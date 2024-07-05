from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2

app = FastAPI()


class User(BaseModel):
    username: str
    email: str
    preferences: dict


@app.post("/register")
async def register(user: User):
    # Save user data to the database
    return {"message": "User registered successfully"}


@app.put("/preferences")
async def update_preferences(user: User):
    # Update user preferences in the database
    return {"message": "Preferences updated successfully"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
