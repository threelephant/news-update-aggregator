import pika
import json
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)


def publish_to_queue(username: str, preferences: list):
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='news_queue')

    message = {"username": username, "preferences": preferences}
    channel.basic_publish(exchange='', routing_key='news_queue', body=json.dumps(message))
    connection.close()


def cache_news(username: str, news: str):
    redis_client.set(username, news)


def get_cached_news(username: str):
    return redis_client.get(username)
