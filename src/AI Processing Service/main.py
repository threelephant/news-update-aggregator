from fastapi import FastAPI
from pydantic import BaseModel
import pika
import json

app = FastAPI()


class News(BaseModel):
    title: str
    content: str


@app.post("/generate-summary")
async def generate_summary(news: News):
    summary = "Generated Summary"  # Replace with actual AI call to GPT
    return {"summary": summary}


def callback(ch, method, properties, body):
    news_data = json.loads(body)
    # Process news data and generate summaries
    summaries = []
    for news in news_data['results']:
        summary = "Generated Summary"  # Replace with actual AI call to GPT
        summaries.append({"title": news['title'], "summary": summary})

    # Publish to RabbitMQ
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='summary_queue')
    channel.basic_publish(exchange='', routing_key='summary_queue', body=json.dumps(summaries))
    connection.close()


@app.on_event("startup")
async def startup_event():
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='news_queue')
    channel.basic_consume(queue='news_queue', on_message_callback=callback, auto_ack=True)
    channel.start_consuming()


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5003)
