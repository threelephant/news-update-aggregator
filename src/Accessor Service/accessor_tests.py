import sys
from pathlib import Path
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app, get_db, User
from database import Base

DATABASE_URL = "postgresql://user:password@localhost/dbname"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)

def test_save_preferences(client):
    response = client.post("/preferences", json={"username": "testuser", "preferences": ["tech", "science"]})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "Preferences saved."

def test_request_news(client):
    response = client.post("/news", json={"username": "testuser", "preferences": ["tech", "science"]})
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "News request initiated."
