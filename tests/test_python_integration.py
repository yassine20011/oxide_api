import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from oxide_api import rust_route

app = FastAPI()

@app.get("/users/{user_id}")
@rust_route("get_user")
def get_user(user_id: int):
    return {"user_id": user_id, "name": "Alice"}

@app.post("/users")
@rust_route("create_user")
def create_user(user: dict):
    return {"message": "User created", "user": user}

client = TestClient(app)

def test_get_user():
    response = client.get("/users/123")
    assert response.status_code == 200
    assert response.json() == {"user_id": 123, "name": "Alice"}

def test_get_user_invalid_int():
    response = client.get("/users/invalid_int")
    assert response.status_code == 422
    data = response.json()
    assert data["ok"] is False
    assert any("user_id" in err for err in data["errors"])

def test_get_nonexistent_route():
    response = client.get("/nonexistent")
    assert response.status_code == 404

def test_post_user_valid():
    payload = {"name": "Alice", "age": 30}
    response = client.post("/users", json=payload)
    assert response.status_code == 200
    assert response.json() == {"message": "User created", "user": payload}

def test_post_user_invalid():
    payload_missing_name = {"age": 30}
    response1 = client.post("/users", json=payload_missing_name)
    assert response1.status_code == 422
    assert response1.json()["ok"] is False

    payload_negative_age = {"name": "Alice", "age": -5}
    response2 = client.post("/users", json=payload_negative_age)
    assert response2.status_code == 422
    assert response2.json()["ok"] is False

def test_openapi_fallback():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "/users/{user_id}" in data["paths"]