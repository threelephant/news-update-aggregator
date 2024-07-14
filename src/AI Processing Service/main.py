import asyncio
import json
import os

import pika
from fastapi import FastAPI
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Get RabbitMQ URL from environment variable
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


class News(BaseModel):
    title: str
    content: str


@app.post("/generate-summary")
async def generate_summary(news: News):
    genai.configure(api_key="AIzaSyAca8llHH2BFvcROKDCmBVGAyrxJR2cZI0")

    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    response = model.generate_content("Hello, tell me please a story").text

    return {"summary": response}


def process_news(ch, method, properties, body):
    news_data = json.loads(body)
    summaries = [{"title": news['title'], "summary": "Generated Summary"} for news in news_data['results']]

    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue='summary_queue')
    channel.basic_publish(exchange='', routing_key='summary_queue', body=json.dumps(summaries))
    connection.close()


async def rabbitmq_listener():
    loop = asyncio.get_event_loop()
    connection = await loop.run_in_executor(None, lambda: pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL)))
    channel = connection.channel()
    channel.queue_declare(queue='news_queue')
    channel.basic_consume(queue='news_queue', on_message_callback=process_news, auto_ack=True)
    await loop.run_in_executor(None, channel.start_consuming)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(rabbitmq_listener())


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5003)
