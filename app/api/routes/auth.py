from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
import aiosqlite
from jose import JWTError, jwt
import os

from app.db.models import UserCreate
from app.services.auth_services import hash_password, verify_password, create_access_token

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    redirect_slashes=False
)

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_TO_A_VERY_LONG_RANDOM_STRING_IN_PRODUCTION")
ALGORITHM = "HS256"

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "schedule.sql")


def _db_path() -> str:
    """Абсолютный путь к БД чтобы не зависеть от рабочей директории"""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base, "..", "..", "..", "schedule.sql"))


# ====================== ЗАВИСИМОСТЬ ДЛЯ ЗАЩИЩЁННЫХ МАРШРУТОВ ======================
async def get_current_user(request: Request):
    """
    Жёсткая проверка — кидает 401 если нет валидного токена.
    Используется только там где страница строго закрыта.
    """
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Неверный токен")
    except JWTError:
        raise HTTPException(status_code=401, detail="Неверный или просроченный токен")

    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            "SELECT id, username FROM users WHERE username = ?", (username,)
        ) as cursor:
            user = await cursor.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return {"id": user[0], "username": user[1]}


async def get_optional_user(request: Request):
    """
    Мягкая проверка - возвращает None если пользователь не авторизован.
    Используется для страниц доступных всем (гостевой режим).
    """
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

    try:
        async with aiosqlite.connect(_db_path()) as db:
            async with db.execute(
                "SELECT id, username FROM users WHERE username = ?", (username,)
            ) as cursor:
                user = await cursor.fetchone()
        if user:
            return {"id": user[0], "username": user[1]}
    except Exception:
        pass

    return None


# ====================== РЕГИСТРАЦИЯ ======================
@router.post("/register")
async def register(user_create: UserCreate):
    if len(user_create.username.strip()) < 3:
        raise HTTPException(status_code=422, detail="Логин должен быть минимум 3 символа")
    if len(user_create.password) < 6:
        raise HTTPException(status_code=422, detail="Пароль должен быть минимум 6 символов")

    async with aiosqlite.connect(_db_path()) as db:
        # Проверяем не занят ли логин
        async with db.execute(
            "SELECT id FROM users WHERE username = ?", (user_create.username.strip(),)
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")

        try:
            hashed = hash_password(user_create.password)
            await db.execute(
                "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
                (user_create.username.strip(), hashed)
            )
            await db.commit()
            return {"msg": "Аккаунт успешно создан"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка при создании аккаунта: {str(e)}")


# ====================== ВХОД ======================
@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    response: Response
):
    async with aiosqlite.connect(_db_path()) as db:
        async with db.execute(
            "SELECT id, hashed_password FROM users WHERE username = ?",
            (form_data.username.strip(),)
        ) as cursor:
            row = await cursor.fetchone()

    # Намеренно одинаковое сообщение для безопасности
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль"
        )

    if not verify_password(form_data.password, row[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль"
        )

    token = create_access_token(data={"sub": form_data.username.strip()})

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,  # 7 дней
        samesite="lax",
        secure=False  # True в продакшене с HTTPS
    )

    return {"message": "Успешный вход", "redirect": "/"}


# ====================== ВЫХОД ======================
@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", samesite="lax")
    return {"message": "Вы вышли из аккаунта"}


# ====================== ПРОВЕРКА СТАТУСА ======================
@router.get("/me")
async def get_me(request: Request):
    """Возвращает текущего пользователя или null — для JS"""
    user = await get_optional_user(request)
    if user:
        return {"authenticated": True, "username": user["username"]}
    return {"authenticated": False, "username": None}