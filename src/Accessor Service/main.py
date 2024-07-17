import os
import logging
import random
import ssl
import threading
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import aioredis
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
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

# Setup FastAPI app
app = FastAPI()
dapr_app = DaprApp(app)

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(level=logging.INFO, filename='logs/accessor.log',
                    format='%(asctime)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", 'redis://localhost')

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


class UserPreferences(BaseModel):
    username: str
    Authorization: str


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
def save_preferences(user_prefs: UserPreferences, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")

    try:
        payload = jwt.decode(user_prefs.Authorization, SECRET_KEY, algorithms=[ALGORITHM])
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
    # credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    # try:
    #     payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    #     username = payload.get("sub")
    #     if username is None:
    #         raise credentials_exception
    # except JWTError:
    #     raise credentials_exception
    #
    # if user_prefs.username != username:
    #     raise HTTPException(status_code=403, detail="Not authorized to request news.")

    background_tasks.add_task(handle_news_request, user_prefs)

    return {"status": "News request initiated."}


# RabbitMQ callback
def process_news_request(ch, method, properties, body):
    asyncio.run(handle_news_request(body))


async def generate_summary(news, categories):
    genai.configure(api_key=GEMINI_AI)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    logger.info(news)
    try:
        response = model.generate_content(f"Please pick the most interesting news based on my preferences and "
                                          f"generate concise summaries: {categories}\n\n "
                                          f"Here are the news:\n {news}").text
    except Exception:
        return None

    return response


def get_user_preferences(db: Session, username: str):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.preferences


async def handle_news_request(body):
    message = json.loads(body)
    username = message['username']

    # username = body.username
    db = SessionLocal()
    try:
        preferences = get_user_preferences(db, username)
    finally:
        db.close()

    categories = " OR ".join(preferences)

    cache = aioredis.from_url(REDIS_URL)
    cached_news = await cache.get(username)
    if cached_news is not None:
        logger.info("Cache hit")
        news_data = json.loads(cached_news)["results"]
    else:
        logger.info("Cache miss")
        news_data = fetch_news(categories)
        await cache.set(username, json.dumps(news_data), ex=7200)

    formatted_news = "\n".join([f"Title: {item['title']}\nDescription: {item['description']}"
                                for item in news_data["results"]])
    summary = await generate_summary(formatted_news, categories)

    send_email(username, summary)
    logger.info(f"Analyzed news for {username}: {summary}")


def fetch_news(category: str):
    response = requests.get(f"https://newsdata.io/api/1/latest?apikey={NEWS_DATA_API}&language=en&q={category}")
    return response.json()


def send_email(username: str, analyzed_news: str):
    logger.info(f"Sending starting, {username}")
    email_sender = os.environ.get("EMAIL_SENDER")
    email_password = os.environ.get("EMAIL_PASSWORD")
    email_receiver = os.environ.get("EMAIL_RECEIVER")

    email_body = f"Hello {username},\n\nHere is your news summary:\n\n{analyzed_news}\n\nBest regards,\nNews Aggregator"

    logger.info(f"Body email: {email_body}")
    msg = MIMEText(email_body)
    msg['Subject'] = 'Your News Summary'
    msg['From'] = email_sender
    msg['To'] = email_receiver

    context = ssl.create_default_context()
    logger.info(SMTP_SERVER)
    logger.info(SMTP_PORT)
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
        server.login(email_sender, email_password)
        server.sendmail(email_sender, email_receiver, msg.as_string())
        logger.info(f"Email sent to {username}")


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5005)
    logger.info("Accessor Service started")
