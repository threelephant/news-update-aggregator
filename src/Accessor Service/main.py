from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .schemas import UserPreferences
from .utils import publish_to_queue, get_cached_news, cache_news
import redis

app = FastAPI()
cache = redis.Redis(host='localhost', port=6379, db=0)


@app.post("/preferences")
async def save_preferences(user_preferences: UserPreferences, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_preferences.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Save preferences to database (implement the logic)
    user.preferences = user_preferences.preferences
    db.commit()

    return {"status": "Preferences saved."}


@app.post("/news")
async def request_news(username: str, preferences: list, db: Session = Depends(get_db)):
    # Publish to RabbitMQ
    publish_to_queue(username, preferences)
    return {"status": "News request initiated."}
