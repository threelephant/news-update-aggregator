import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pika
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

rabbitmq_url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672")
email_user = os.getenv("EMAIL_USER", "your-email@example.com")
email_password = os.getenv("EMAIL_PASSWORD", "your-email-password")
telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "your-telegram-bot-token")
telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "your-telegram-chat-id")


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


def callback(ch, method, properties, body):
    notification_data = json.loads(body)
    for notification in notification_data:
        send_email(notification['recipient'], notification['message'])


@app.on_event("startup")
async def startup_event():
    connection_parameters = pika.URLParameters(rabbitmq_url)
    connection = pika.BlockingConnection(connection_parameters)
    channel = connection.channel()
    channel.queue_declare(queue='notification_queue')
    channel.basic_consume(queue='notification_queue', on_message_callback=callback, auto_ack=True)
    print("Started consuming from notification_queue")
    channel.start_consuming()


@app.get("/")
def read_root():
    return {"message": "Notification Service is running"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5004)
