from fastapi import FastAPI
from pydantic import BaseModel
import requests
import pika
import json

app = FastAPI()


class Preferences(BaseModel):
    categories: list
    languages: list


@app.post("/fetch-news")
async def fetch_news(preferences: Preferences):
    response = requests.get('https://newsdata.io/api/1/news', params={"apikey": "YOUR_API_KEY", **preferences.dict()})
    news_data = response.json()

    # Publish to RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='news_queue')
    channel.basic_publish(exchange='', routing_key='news_queue', body=json.dumps(news_data))
    connection.close()

    return {"status": "News data sent to AI Processing Service"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5002)
