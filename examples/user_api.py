from fastapi import FastAPI
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)