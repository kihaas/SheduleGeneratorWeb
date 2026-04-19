from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from typing import Optional

# Фикс совместимости bcrypt + passlib (bcrypt >= 4.0 убрал __about__)
import bcrypt as _bcrypt_module
if not hasattr(_bcrypt_module, '__about__'):
    class _FakeAbout:
        __version__ = _bcrypt_module.__version__
    _bcrypt_module.__about__ = _FakeAbout()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_THIS_TO_A_VERY_LONG_RANDOM_STRING_IN_PRODUCTION")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)