import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from oxide_api import rust_route

app = FastAPI()

@app.get("/users/{user_id}")
@rust_route("get_user")
def get_user(user_id: int):
    return {"user_id": user_id, "name": "Alice"}

client = TestClient(app)

def test_get_user():
    response = client.get("/users/123")
    assert response.status_code == 200
    assert response.json() == {"user_id": 123, "name": "Alice"}

def test_get_user_not_found():
    response = client.get("/users/999")
    assert response.status_code == 404

def test_get_user_invalid_id():
    response = client.get("/users/abc")
    assert response.status_code == 422