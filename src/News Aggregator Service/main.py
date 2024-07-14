import requests
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

news_api = 'pub_47925cee563b6e01a191693abcbb2b7ae99ad'
load_dotenv()
app = FastAPI()


class Preferences(BaseModel):
    category: str


@app.post("/fetch-news")
async def fetch_news(preferences: Preferences):
    response = requests.get(f'https://newsdata.io/api/1/latest?apikey={news_api}&q={preferences.category}')
    news_data = response.json()
    return news_data
    # Publish to RabbitMQ
    # connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    # channel = connection.channel()
    # channel.queue_declare(queue='news_queue')
    # channel.basic_publish(exchange='', routing_key='news_queue', body=json.dumps(news_data))
    # connection.close()
    #
    # return {"status": "News data sent to AI Processing Service"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5002)
