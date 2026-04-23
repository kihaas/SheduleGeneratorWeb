from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "Schedule Generator"

    # Основной путь к БД (можно переопределять в .env)
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/schedule.sql"

    # Дополнительные часто используемые переменные (чтобы не падало)
    SECRET_KEY: str = "CHANGE_THIS_TO_A_VERY_LONG_RANDOM_STRING_IN_PRODUCTION"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ← Это главное исправление
        case_sensitive=True,
    )

    @property
    def DB_PATH(self) -> str:
        """Извлекаем чистый путь к файлу SQLite из DATABASE_URL"""
        url = self.DATABASE_URL
        if url.startswith("sqlite+aiosqlite:///"):
            path = url.replace("sqlite+aiosqlite:///", "")
            # Если путь относительный — делаем абсолютный относительно корня проекта
            if not os.path.isabs(path):
                base_dir = Path(__file__).parent.parent.parent
                path = str(base_dir / path)
            return path
        # Fallback
        return os.getenv("DB_PATH", str(Path("data/schedule.sql").resolve()))


# Глобальный экземпляр
settings = Settings()