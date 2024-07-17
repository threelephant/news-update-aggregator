import pytest
import requests

# Base URL for the API
BASE_URL = "http://localhost:5004"

# Test data
user_data = {"username": "testuser", "password": "testpassword"}
preferences_data = {"username": "testuser", "preferences": ["tech", "news"]}


@pytest.fixture
def get_token():
    response = requests.post(f"{BASE_URL}/token", data=user_data)
    assert response.status_code == 200
    return response.json()["access_token"]


def test_register_user():
    response = requests.post(f"{BASE_URL}/register", json=user_data)
    assert response.status_code == 201
    assert response.json()["username"] == user_data["username"]


def test_login_user():
    response = requests.post(f"{BASE_URL}/token", data=user_data)
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_save_preferences(get_token):
    token = get_token
    response = requests.post(
        f"{BASE_URL}/preferences",
        json=preferences_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "Preferences saved."}


def test_request_news(get_token):
    token = get_token
    response = requests.post(
        f"{BASE_URL}/news?username=testuser",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "News request sent to queue."}
