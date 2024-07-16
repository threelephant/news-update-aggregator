import logging
import os
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import requests

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Log to terminal
        RotatingFileHandler('logs/app.log', maxBytes=10 * 1024 * 1024, backupCount=3)  # Log to file
    ]
)

logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(root_path="/api")

# Security settings
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2PasswordBearer for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str


class UserPreferences(BaseModel):
    username: str
    preferences: list[str]


class Token(BaseModel):
    access_token: str
    token_type: str


# Environment Variables for Accessor Service
ACCESSOR_SERVICE_URL = os.getenv("ACCESSOR_SERVICE_URL", "http://localhost:5005")


# Routes
@app.post("/register", response_model=UserCreate, status_code=201)
def register(user: UserCreate):
    response = requests.post(f"{ACCESSOR_SERVICE_URL}/register", json=user.dict())
    if response.status_code != 201:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    return response.json()


@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    response = requests.post(f"{ACCESSOR_SERVICE_URL}/token",
                             data={"username": form_data.username, "password": form_data.password})
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    return response.json()


@app.post("/preferences", response_model=dict)
def save_preferences(user_prefs: UserPreferences, token: str = Depends(oauth2_scheme)):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{ACCESSOR_SERVICE_URL}/save_preferences", json=user_prefs.dict(), headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    return response.json()


@app.post("/news", response_model=dict)
def request_news(user_prefs: UserPreferences, background_tasks: BackgroundTasks, token: str = Depends(oauth2_scheme)):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{ACCESSOR_SERVICE_URL}/news", json=user_prefs.dict(), headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())
    return response.json()


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5004)
