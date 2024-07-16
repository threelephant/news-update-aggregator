import asyncio

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
import requests
import genai
from database import SessionLocal, engine, Base
from models import User, News, Preferences
import redis
import json
import pika
import logging
import os

# Initialize FastAPI app
app = FastAPI()

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')
logging.basicConfig(level=logging.INFO, filename='logs/accessor.log',
                    format='%(asctime)s:%(levelname)s:%(message)s')
logger = logging.getLogger(__name__)

# Setup Redis for caching
cache = redis.Redis(host='localhost', port=6379, db=0)

# Setup Database
Base.metadata.create_all(bind=engine)

# Setup RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='news_queue')

# Environment Variables
NEWS_DATA_API = os.getenv("NEWS_DATA_API")
GEMINI_AI = os.getenv("GEMINI_AI")


# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/validate_credentials")
async def validate_credentials(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if user and user.verify_password(password):
        return {"token": "fake-jwt-token"}  # You should replace with real JWT token
    raise HTTPException(status_code=400, detail="Invalid credentials")


@app.post("/save_preferences")
async def save_preferences(username: str, preferences: Preferences, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if user:
        user.preferences = json.dumps(preferences.dict())
        db.commit()
        return {"status": "Preferences saved"}
    raise HTTPException(status_code=400, detail="User not found")


@app.post("/news")
async def request_news(username: str, preferences: Preferences, db: Session = Depends(get_db)):
    # Publish to RabbitMQ
    publish_to_queue(username, preferences)
    return {"status": "News request initiated."}


@app.post("/process_news")
async def process_news(username: str, news: News):
    # Analyze and summarize news using AI
    analyzed_news = await generate_summary(news)
    return analyzed_news


async def fetch_news(preferences: Preferences):
    response = requests.get(f'https://newsdata.io/api/1/latest?apikey={NEWS_DATA_API}&q={preferences.category}')
    news_data = response.json()
    return news_data


async def generate_summary(news: News):
    genai.configure(api_key=GEMINI_AI)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    response = model.generate_content(news.content).text
    return {"summary": response}


def publish_to_queue(username: str, preferences: Preferences):
    message = {"username": username, "preferences": preferences.dict()}
    channel.basic_publish(exchange='', routing_key='news_queue', body=json.dumps(message))
    logger.info(f"Published to queue: {message}")


def process_news_request(ch, method, properties, body):
    asyncio.run(handle_news_request(body))


async def handle_news_request(body):
    message = json.loads(body)
    username = message['username']
    preferences = Preferences(**message['preferences'])

    # Check cache
    cached_news = cache.get(username)
    if cached_news:
        logger.info("Cache hit")
        news_data = json.loads(cached_news)
    else:
        logger.info("Cache miss")
        news_data = await fetch_news(preferences)
        cache.set(username, json.dumps(news_data))

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
