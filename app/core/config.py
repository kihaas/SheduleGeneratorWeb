from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    PROJECT_NAME: str = "Schedule Generator"
    DATABASE_URL: str = "sqlite+aiosqlite:///./schedule.db"

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
