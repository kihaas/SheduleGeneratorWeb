import aiosqlite
from pathlib import Path
import os


class Database:
    def __init__(self, db_path: str = "schedule.sql"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._conn = None
        self._initialized = False

    async def _get_connection(self):
        """Создать новое соединение (вызывается для каждого запроса)"""
        conn = await aiosqlite.connect(self.db_path)
        await conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # В class Database добавьте:
    async def fetch_all(self, query: str, params: tuple = None):
        """Получить все строки"""
        conn = await self._get_connection()
        try:
            if params:
                cursor = await conn.execute(query, params)
            else:
                cursor = await conn.execute(query)
            rows = await cursor.fetchall()
            await cursor.close()
            return rows
        except Exception as e:
            raise e
        finally:
            await conn.close()

    async def fetch_one(self, query: str, params: tuple = None):
        """Получить одну строку"""
        conn = await self._get_connection()
        try:
            if params:
                cursor = await conn.execute(query, params)
            else:
                cursor = await conn.execute(query)
            row = await cursor.fetchone()
            await cursor.close()
            return row
        except Exception as e:
            raise e
        finally:
            await conn.close()

    async def execute(self, query: str, params: tuple = None):
        """Выполнить запрос"""
        conn = await self._get_connection()
        try:
            if params:
                result = await conn.execute(query, params)
            else:
                result = await conn.execute(query)
            await conn.commit()
            return result
        except Exception as e:
            await conn.rollback()
            raise e
        finally:
            await conn.close()

    async def init_db(self):
        """Инициализация базы данных"""
        if self._initialized:
            return

        print("🔄 Инициализация базы данных...")

        try:
            # Создаем файл базы если не существует
            if not self.db_path.exists():
                print("🆕 Создаем новую базу данных...")
                conn = await self._get_connection()
                await conn.close()

            conn = await self._get_connection()

            # Проверяем существование таблиц
            tables = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = [row[0] for row in await tables.fetchall()]
            await tables.close()

            if 'subjects' not in existing_tables:
                print("📦 Создаем структуру базы данных с новой архитектурой...")

                # ТАБЛИЦА ГРУПП
                await conn.execute('''
                    CREATE TABLE study_groups (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Таблица преподавателей - БЕЗ group_id (ГЛОБАЛЬНЫЕ)
                await conn.execute('''
                    CREATE TABLE teachers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                await conn.execute('''
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        hashed_password TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                ''')


                # Таблица предметов - С group_id (ЛОКАЛЬНЫЕ ДЛЯ ГРУППЫ)
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS subjects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        teacher TEXT NOT NULL,
                        subject_name TEXT NOT NULL,
                        total_hours INTEGER NOT NULL DEFAULT 0,
                        remaining_hours INTEGER NOT NULL DEFAULT 0,
                        remaining_pairs INTEGER NOT NULL DEFAULT 0,
                        priority INTEGER DEFAULT 0,
                        max_per_day INTEGER DEFAULT 2,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        group_id INTEGER DEFAULT 1,
                        min_per_week INTEGER DEFAULT 1,
                        max_per_week INTEGER DEFAULT 20,
                        UNIQUE(teacher, subject_name, group_id)
                    )
                ''')

                try:
                    await conn.execute('ALTER TABLE subjects ADD COLUMN min_per_week INTEGER DEFAULT 1')
                    await conn.execute('ALTER TABLE subjects ADD COLUMN max_per_week INTEGER DEFAULT 20')
                except Exception as e:
                    print(f"⚠️ Колонки уже существуют или ошибка: {e}")

                # Таблица занятий - С group_id (ЛОКАЛЬНЫЕ ДЛЯ ГРУППЫ)
                await conn.execute('''
                    CREATE TABLE lessons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        day INTEGER NOT NULL CHECK(day >= 0 AND day <= 6),
                        time_slot INTEGER NOT NULL CHECK(time_slot >= 0 AND time_slot <= 3),
                        teacher TEXT NOT NULL,
                        subject_name TEXT NOT NULL,
                        editable BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        group_id INTEGER DEFAULT 1,
                        UNIQUE(day, time_slot, group_id)
                    )
                ''')

                # Таблица фильтров - БЕЗ group_id (ГЛОБАЛЬНЫЕ)
                await conn.execute('''
                            CREATE TABLE negative_filters (
                                teacher TEXT PRIMARY KEY,
                                restricted_days TEXT DEFAULT '[]',
                                restricted_slots TEXT DEFAULT '[]',
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')

                # Таблица сохраненных расписаний - С group_id
                await conn.execute('''
                    CREATE TABLE saved_schedules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        name TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        payload TEXT NOT NULL,
                        group_id INTEGER DEFAULT 1
                    )
                ''')

                # Индексы для производительности
                await conn.execute('CREATE INDEX idx_subjects_teacher ON subjects(teacher)')
                await conn.execute('CREATE INDEX idx_lessons_day_time ON lessons(day, time_slot)')
                await conn.execute('CREATE INDEX idx_teachers_name ON teachers(name)')
                await conn.execute('CREATE INDEX idx_group_id_subjects ON subjects(group_id)')
                await conn.execute('CREATE INDEX idx_group_id_lessons ON lessons(group_id)')

                # Добавляем основную группу
                await conn.execute('INSERT INTO study_groups (id, name) VALUES (1, "Основная")')

                await conn.commit()
                print("✅ База данных создана с новой архитектурой (преподаватели глобальные)")
            else:
                print("✅ База данных уже инициализирована, применяем миграцию...")
                await self._migrate_to_new_architecture(conn)

            self._initialized = True

        except Exception as e:
            print(f"❌ Ошибка инициализации базы данных: {e}")
            raise
        finally:
            if 'conn' in locals():
                await conn.close()

    async def _migrate_to_new_architecture(self, conn):
        """Миграция на новую архитектуру (фильтры глобальные)"""
        try:
            print("🔄 Проверяем миграцию фильтров...")

            # Проверяем есть ли group_id в negative_filters
            columns = await conn.execute("PRAGMA table_info(negative_filters)")
            column_info = await columns.fetchall()
            column_names = [col[1] for col in column_info]

            print(f"📊 Колонки negative_filters: {column_names}")

            if 'group_id' in column_names:
                print("🔄 Миграция: делаем фильтры глобальными...")

                # 1. Создаем временную таблицу с текущими данными
                await conn.execute('''
                    CREATE TABLE temp_negative_filters AS 
                    SELECT DISTINCT teacher, restricted_days, restricted_slots, created_at 
                    FROM negative_filters 
                    WHERE teacher IS NOT NULL
                ''')

                # 2. Удаляем старую таблицу
                await conn.execute('DROP TABLE negative_filters')

                # 3. Создаем новую таблицу без group_id
                await conn.execute('''
                    CREATE TABLE negative_filters (
                        teacher TEXT PRIMARY KEY,
                        restricted_days TEXT DEFAULT '[]',
                        restricted_slots TEXT DEFAULT '[]',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # 4. Копируем данные из временной таблицы
                await conn.execute('''
                    INSERT OR REPLACE INTO negative_filters (teacher, restricted_days, restricted_slots, created_at)
                    SELECT teacher, restricted_days, restricted_slots, created_at 
                    FROM temp_negative_filters
                ''')

                # 5. Удаляем временную таблицу
                await conn.execute('DROP TABLE temp_negative_filters')

                await conn.commit()
                print("✅ Фильтры успешно мигрированы в глобальную таблицу")
            else:
                print("✅ Таблица negative_filters уже глобальная")

            # 6. Проверяем остальные таблицы
            print("🔄 Проверяем другие таблицы...")

            # Проверяем subjects
            subjects_columns = await conn.execute("PRAGMA table_info(subjects)")
            subs_cols = [col[1] for col in await subjects_columns.fetchall()]
            print(f"📊 Колонки subjects: {subs_cols}")

            # Проверяем lessons
            lessons_columns = await conn.execute("PRAGMA table_info(lessons)")
            less_cols = [col[1] for col in await lessons_columns.fetchall()]
            print(f"📊 Колонки lessons: {less_cols}")

            print("✅ Миграция проверена")

        except Exception as e:
            print(f"⚠️ Ошибка миграции: {e}")
            import traceback
            print(f"⚠️ Traceback: {traceback.format_exc()}")


# Глобальный экземпляр базы данных
database = Database()