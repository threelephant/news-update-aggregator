import os
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request, Body
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
import requests
import redis
import pika
import json
import asyncio
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from dapr.ext.fastapi import DaprApp

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Environment Variables for External APIs
NEWS_DATA_API = os.getenv("NEWS_DATA_API")
GEMINI_AI = os.getenv("GEMINI_API_KEY")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "user@example.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "password")

# Setup FastAPI app
app = FastAPI()
dapr_app = DaprApp(app)

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(level=logging.INFO, filename='logs/accessor.log',
                    format='%(asctime)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

# Setup Redis for caching
cache = redis.Redis(host='localhost', port=6379, db=0)

# Setup RabbitMQ
logger.debug(RABBITMQ_URL)
connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
channel = connection.channel()
channel.queue_declare(queue='news_queue')

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:15432/dbname")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Security settings
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2PasswordBearer for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Database models
class User(Base):
    __tablename__ = "users"
    username = Column(String, primary_key=True, index=True)
    password = Column(String)
    preferences = Column(JSON, nullable=True)


Base.metadata.create_all(bind=engine)


# Helper functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic models
class Preferences(BaseModel):
    category: str


class News(BaseModel):
    content: str


class UserCreate(BaseModel):
    username: str
    password: str
    email: str  # Add email to user creation


class UserPreferences(BaseModel):
    username: str
    preferences: list[str]


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str


@app.post("/register", response_model=UserCreate, status_code=201)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="User already exists.")

    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/save_preferences", response_model=dict)
def save_preferences(user_prefs: UserPreferences, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if user_prefs.username != username:
        raise HTTPException(status_code=403, detail="Not authorized to update preferences.")

    user = db.query(User).filter(User.username == username).first()
    user.preferences = user_prefs.preferences
    db.commit()
    db.refresh(user)
    return {"status": "Preferences saved."}


@dapr_app.subscribe(pubsub='rabbitmq-pubsub', topic='news-queue')
def news_handler(event_data=Body()):
    message = event_data["data"]
    logger.info(message)
    asyncio.run(handle_news_request(message))


@app.post("/news", response_model=dict)
async def request_news(user_prefs: UserPreferences, background_tasks: BackgroundTasks, db: Session = Depends(get_db),
                       token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if user_prefs.username != username:
        raise HTTPException(status_code=403, detail="Not authorized to request news.")

    background_tasks.add_task(handle_news_request, user_prefs)

    return {"status": "News request initiated."}


# RabbitMQ callback
def process_news_request(ch, method, properties, body):
    asyncio.run(handle_news_request(body))


async def generate_summary(news: News):
    genai.configure(api_key=GEMINI_AI)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    logger.info(news.content)
    try:
        response = model.generate_content(f"Provide short summary of this news: {news.content}").text
    except Exception:
        return None

    # await asyncio.sleep(10)
    return {"summary": response}


async def handle_news_request(body):
    message = json.loads(body)
    username = message['username']
    preferences = message['preferences']
    # username = body.username
    # preferences = body.preferences

    categories = "&".join(preferences)

    # Check cache
    # cached_news = await cache.get(username)
    # if cached_news:
    #     logger.info("Cache hit")
    #     news_data = json.loads(cached_news)
    # else:
    #     logger.info("Cache miss")
    news_data = fetch_news(categories)
    # await cache.set(username, json.dumps(news_data))

    # Analyze news using AI
    analyzed_news = []
    for news in news_data["results"]:
        if news["description"] is not None:
            summary = await generate_summary(News(content=news['description']))
            if summary is not None:
                analyzed_news.append(await generate_summary(News(content=news['description'])))

    # send_email(username, analyzed_news)
    logger.info(f"Analyzed news for {username}: {analyzed_news}")


def fetch_news(category: str):
    # Simulate fetching news from an external API
    response = requests.get(f"https://newsdata.io/api/1/latest?apikey={NEWS_DATA_API}&q={category}")
    return response.json()


def send_email(username: str, analyzed_news: list):
    # Fetch user email from the database
    db = next(get_db())
    user = db.query(User).filter(User.username == username).first()
    if not user:
        logger.error(f"User {username} not found")
        return

    email_body = f"Hello {username},\n\nHere is your news summary:\n\n{' '.join(analyzed_news)}\n\nBest regards,\nNews Aggregator"
    msg = MIMEText(email_body)
    msg['Subject'] = 'Your News Summary'
    msg['From'] = SMTP_USERNAME
    msg['To'] = user.email

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, [user.email], msg.as_string())
        logger.info(f"Email sent to {username}")


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5005)
    logger.info("Accessor Service started")
