from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from jose import JWTError, jwt
import os

from app.db.database import database          # ← используем наш класс
from app.db.models import UserCreate
from app.services.auth_services import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"], redirect_slashes=False)

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_TO_A_VERY_LONG_RANDOM_STRING_IN_PRODUCTION")
ALGORITHM = "HS256"

# ====================== ЗАВИСИМОСТИ ======================
async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Неверный токен")
    except JWTError:
        raise HTTPException(status_code=401, detail="Неверный или просроченный токен")

    # Через наш Database класс
    row = await database.fetch_one(
        "SELECT id, username FROM users WHERE username = ?",
        (username,)
    )
    if not row:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return {"id": row[0], "username": row[1]}


async def get_optional_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            return None
    except JWTError:
        return None

    row = await database.fetch_one(
        "SELECT id, username FROM users WHERE username = ?",
        (username,)
    )
    if row:
        return {"id": row[0], "username": row[1]}
    return None


# ====================== РЕГИСТРАЦИЯ ======================
@router.post("/register")
async def register(user_create: UserCreate):
    if len(user_create.username.strip()) < 3:
        raise HTTPException(status_code=422, detail="Логин должен быть минимум 3 символа")
    if len(user_create.password) < 6:
        raise HTTPException(status_code=422, detail="Пароль должен быть минимум 6 символов")

    # Проверка существования
    existing = await database.fetch_one(
        "SELECT id FROM users WHERE username = ?",
        (user_create.username.strip(),)
    )
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")

    hashed = hash_password(user_create.password)
    await database.execute(
        "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
        (user_create.username.strip(), hashed)
    )

    return {"msg": "Аккаунт успешно создан"}


# ====================== ВХОД ======================
@router.post("/login")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], response: Response):
    row = await database.fetch_one(
        "SELECT id, hashed_password FROM users WHERE username = ?",
        (form_data.username.strip(),)
    )

    if not row or not verify_password(form_data.password, row[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль"
        )

    token = create_access_token(data={"sub": form_data.username.strip()})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,
        samesite="lax",
        secure=False
    )
    return {"message": "Успешный вход", "redirect": "/"}


# ====================== ВЫХОД ======================
@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", samesite="lax")
    return {"message": "Вы вышли из аккаунта"}


# ====================== СТАТУС ======================
@router.get("/me")
async def get_me(request: Request):
    user = await get_optional_user(request)
    if user:
        return {"authenticated": True, "username": user["username"]}
    return {"authenticated": False, "username": None}