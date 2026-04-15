from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Annotated, Optional
import aiosqlite

from app.db.database import database  # твоя функция подключения
from app.services.auth_services import (
    hash_password,
    verify_password,
    create_access_token,
    SECRET_KEY,
    ALGORITHM
)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    # Проверяем, существует ли пользователь
    async with aiosqlite.connect("schedule.sql") as db:   # замени на твою DB_PATH
        async with db.execute("SELECT id, username FROM users WHERE username = ?", (token_data.username,)) as cursor:
            user = await cursor.fetchone()
            if user is None:
                raise credentials_exception
    return {"id": user[0], "username": user[1]}


@router.post("/register", response_model=dict)
async def register(user_create: "UserCreate"):   # импортируй UserCreate из models
    async with aiosqlite.connect("schedule.sql") as db:
        try:
            hashed = hash_password(user_create.password)
            await db.execute(
                "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
                (user_create.username, hashed)
            )
            await db.commit()
            return {"msg": "User created successfully"}
        except aiosqlite.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail="Username already registered"
            )


@router.post("/login", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    async with aiosqlite.connect("schedule.sql") as db:
        async with db.execute(
            "SELECT hashed_password FROM users WHERE username = ?",
            (form_data.username,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row or not verify_password(form_data.password, row[0]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}