import pika
import json
from sqlalchemy.orm import Session
from database import get_db
from utils import get_cached_news, cache_news
from models import User


def process_news_request(ch, method, properties, body):
    message = json.loads(body)
    username = message['username']

    # Implement logic to retrieve user preferences from DB
    db = get_db()
    user = db.query(User).filter(User.username == username).first()

    if not user:
        print("User not found")
        return

    # Here you would fetch news based on preferences
    news = fetch_news_based_on_preferences(user.preferences)

    # Cache the news
    cache_news(username, news)

    # Send notification logic goes here
    print(f"News for {username}: {news}")


def fetch_news_based_on_preferences(preferences):
    # Mock fetching news based on preferences
    return f"Fetched news for preferences: {preferences}"


def start_worker():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='news_queue')

    channel.basic_consume(queue='news_queue', on_message_callback=process_news_request, auto_ack=True)

    print('Waiting for messages...')
    channel.start_consuming()
