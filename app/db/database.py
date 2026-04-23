import aiosqlite
from pathlib import Path
from app.core.config import settings
import asyncio

class Database:
    def __init__(self):
        self.db_path = Path(settings.DB_PATH).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def _get_connection(self):
        """Новое соединение для каждого запроса + PRAGMA"""
        conn = await aiosqlite.connect(str(self.db_path))
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA journal_mode = WAL")      # важно для надёжности
        return conn

    # === Основные методы ===
    async def fetch_all(self, query: str, params: tuple = None):
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(query, params or ())
            rows = await cursor.fetchall()
            await cursor.close()
            return rows
        finally:
            await conn.close()

    async def fetch_one(self, query: str, params: tuple = None):
        conn = await self._get_connection()
        try:
            cursor = await conn.execute(query, params or ())
            row = await cursor.fetchone()
            await cursor.close()
            return row
        finally:
            await conn.close()

    async def execute(self, query: str, params: tuple = None):
        conn = await self._get_connection()
        try:
            await conn.execute(query, params or ())
            await conn.commit()          # ← обязательно
            return True
        except Exception as e:
            await conn.rollback()
            raise
        finally:
            await conn.close()

    # === Инициализация (усиленная) ===
    async def init_db(self):
        if self._initialized:
            return

        print(f"🔄 Инициализация базы данных → {self.db_path}")

        conn = None
        try:
            conn = await self._get_connection()

            print("📦 Создаём/проверяем таблицы...")

            tables = [
                # study_groups
                '''CREATE TABLE IF NOT EXISTS study_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''',
                # teachers
                '''CREATE TABLE IF NOT EXISTS teachers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''',
                # users — самая важная
                '''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''',
                # subjects
                '''CREATE TABLE IF NOT EXISTS subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher TEXT NOT NULL,
                    subject_name TEXT NOT NULL,
                    total_hours INTEGER NOT NULL DEFAULT 0,
                    remaining_hours INTEGER NOT NULL DEFAULT 0,
                    remaining_pairs INTEGER NOT NULL DEFAULT 0,
                    priority INTEGER DEFAULT 0,
                    max_per_day INTEGER DEFAULT 2,
                    group_id INTEGER DEFAULT 1,
                    min_per_week INTEGER DEFAULT 1,
                    max_per_week INTEGER DEFAULT 20,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(teacher, subject_name, group_id)
                )''',
                # lessons
                '''CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    day INTEGER NOT NULL CHECK(day >= 0 AND day <= 6),
                    time_slot INTEGER NOT NULL CHECK(time_slot >= 0 AND time_slot <= 3),
                    teacher TEXT NOT NULL,
                    subject_name TEXT NOT NULL,
                    editable BOOLEAN DEFAULT 1,
                    group_id INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(day, time_slot, group_id)
                )''',
                # negative_filters (глобальная)
                '''CREATE TABLE IF NOT EXISTS negative_filters (
                    teacher TEXT PRIMARY KEY,
                    restricted_days TEXT DEFAULT '[]',
                    restricted_slots TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''',
                # saved_schedules
                '''CREATE TABLE IF NOT EXISTS saved_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    group_id INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )'''
            ]

            for table_sql in tables:
                await conn.execute(table_sql)

            # Индексы
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_subjects_teacher ON subjects(teacher)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_lessons_day_time ON lessons(day, time_slot)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_group_id_subjects ON subjects(group_id)")

            # Основная группа
            await conn.execute('INSERT OR IGNORE INTO study_groups (id, name) VALUES (1, "Основная")')

            await conn.commit()
            print("🎉 Все таблицы успешно созданы / проверены")

            # Дополнительно: принудительно обновляем схему
            await conn.execute("PRAGMA schema_version")
            await conn.commit()

            self._initialized = True

        except Exception as e:
            print(f"❌ Ошибка инициализации БД: {e}")
            import traceback
            print(traceback.format_exc())
            raise
        finally:
            if conn:
                await conn.close()


# Глобальный экземпляр
database = Database()