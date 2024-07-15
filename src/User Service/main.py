from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:15432/dbname")
print(DATABASE_URL)
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserModel(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    preferences = Column(JSON)
    hashed_password = Column(String)


Base.metadata.create_all(bind=engine)

app = FastAPI()


class User(BaseModel):
    username: str
    email: str
    preferences: dict
    password: str


class UserInDB(User):
    hashed_password: str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/register")
async def register(user: User, db: Session = Depends(get_db)):
    hashed_password = pwd_context.hash(user.password)
    db_user = UserModel(**user.dict(exclude={"password"}), hashed_password=hashed_password)

    try:
        db.add(db_user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="User already exists")

    return {"message": "User registered successfully"}


@app.post("/login")
async def login(user: User, db: Session = Depends(get_db)):
    db_user = db.query(UserModel).filter(UserModel.username == user.username).first()
    if not db_user or not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid username or password")

    return {"message": "Login successful", "username": db_user.username}


@app.get("/users/{username}")
async def get_user(username: str, db: Session = Depends(get_db)):
    db_user = db.query(UserModel).filter(UserModel.username == username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    return {"username": db_user.username, "email": db_user.email, "preferences": db_user.preferences}


@app.put("/preferences/{username}")
async def update_preferences(username: str, user: User, db: Session = Depends(get_db)):
    db_user = db.query(UserModel).filter(UserModel.username == username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db_user.preferences = user.preferences
    db.commit()
    return {"message": "Preferences updated successfully"}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
