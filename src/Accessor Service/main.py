import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
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

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Setup FastAPI app
app = FastAPI()

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(level=logging.INFO, filename='logs/accessor.log',
                    format='%(asctime)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

# Setup Redis for caching
cache = redis.Redis(host='localhost', port=6379, db=0)

# Setup RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
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

# Environment Variables for External APIs
NEWS_DATA_API = os.getenv("NEWS_DATA_API")
GEMINI_AI = os.getenv("GEMINI_AI")


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


@app.post("/news", response_model=dict)
def request_news(user_prefs: UserPreferences, background_tasks: BackgroundTasks, db: Session = Depends(get_db),
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

    # Send the request to the queue (simulated with a background task)
    background_tasks.add_task(fetch_news, username)
    return {"status": "News request initiated."}


def fetch_news(username: str):
    # Here, you would interact with the Accessor Service
    print(f"Fetching news for {username}...")


# RabbitMQ callback
def process_news_request(ch, method, properties, body):
    asyncio.run(handle_news_request(body))


async def generate_summary(news: News):
    genai.configure(api_key=GEMINI_AI)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    response = model.generate_content(news.content).text
    return {"summary": response}


async def handle_news_request(body):
    message = json.loads(body)
    username = message['username']
    preferences = Preferences(**message['preferences'])

    # Check cache
    cached_news = await cache.get(username)
    if cached_news:
        logger.info("Cache hit")
        news_data = json.loads(cached_news)
    else:
        logger.info("Cache miss")
        news_data = fetch_news(preferences.category)
        await cache.set(username, json.dumps(news_data))

    # Analyze news using AI
    analyzed_news = await generate_summary(News(content=news_data['results'][0]['description']))

    # Send notification logic goes here
    logger.info(f"Analyzed news for {username}: {analyzed_news}")


# Consume from RabbitMQ queue
channel.basic_consume(queue='news_queue', on_message_callback=process_news_request, auto_ack=True)

# Start consuming
# logger.info('Waiting for messages. To exit press CTRL+C')
# channel.start_consuming()

if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5005)
