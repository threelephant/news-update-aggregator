import os
import json
import smtplib
import aio_pika
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

app = FastAPI()
load_dotenv()

rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
email_user = os.getenv("EMAIL_USER", "your-email@example.com")
email_password = os.getenv("EMAIL_PASSWORD", "your-email-password")


class Notification(BaseModel):
    recipient: str
    message: str


def send_email(recipient, message):
    msg = MIMEMultipart()
    msg['From'] = email_user
    msg['To'] = recipient
    msg['Subject'] = 'Notification'

    msg.attach(MIMEText(message, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email_user, email_password)
        text = msg.as_string()
        server.sendmail(email_user, recipient, text)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")


async def callback(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    async with message.process():
        notification_data = json.loads(message.body)
        for notification in notification_data:
            send_email(notification['recipient'], notification['message'])


async def consume():
    connection = await aio_pika.connect_robust(rabbitmq_url)
    channel = await connection.channel()
    queue = await channel.declare_queue("notification_queue", durable=True)
    await queue.consume(callback)
    print("Started consuming from notification_queue")


@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    loop.create_task(consume())


@app.get("/")
def read_root():
    return {"message": "Notification Service is running"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5004)
