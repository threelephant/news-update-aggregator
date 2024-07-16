import os

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app, get_db, Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:15432/dbname")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Create a new database session for testing
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


# Test user registration
def test_register(client):
    response = client.post("/register", json={"username": "testuser3", "password": "testpassword"})
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["username"] == "testuser3"


# Test user login
def test_login(client):
    client.post("/register", json={"username": "testuser3", "password": "testpassword"})
    response = client.post("/token", data={"username": "testuser3", "password": "testpassword"})
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()


# Test saving preferences
def test_save_preferences(client):
    client.post("/register", json={"username": "testuser3", "password": "testpassword"})
    login_response = client.post("/token", data={"username": "testuser3", "password": "testpassword"})
    token = login_response.json()["access_token"]

    response = client.post(
        "/preferences",
        json={"username": "testuser3", "preferences": ["tech", "science"]},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "Preferences saved."


# Test requesting news
def test_request_news(client):
    client.post("/register", json={"username": "testuser3", "password": "testpassword"})
    login_response = client.post("/token", data={"username": "testuser3", "password": "testpassword"})
    token = login_response.json()["access_token"]

    response = client.post(
        "/news",
        json={"username": "testuser3", "preferences": ["tech", "science"]},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "News request initiated."
