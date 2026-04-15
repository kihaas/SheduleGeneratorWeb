from app.db.database import database
from app.db.models import StudyGroup, StudyGroupCreate
from typing import List, Optional
import json


class GroupService:
    async def get_all_groups(self) -> List[StudyGroup]:
        """Получить все группы"""
        rows = await database.fetch_all(
            'SELECT id, name, created_at FROM study_groups ORDER BY name'
        )
        return [
            StudyGroup(id=row[0], name=row[1], created_at=row[2])
            for row in rows
        ]

    async def create_group(self, name: str) -> StudyGroup:
        """Создать новую группу"""
        # Проверяем уникальность имени
        existing = await database.fetch_one(
            'SELECT id FROM study_groups WHERE name = ?',
            (name,)
        )
        if existing:
            raise ValueError(f"Группа с именем '{name}' уже существует")

        # Создаем группу
        result = await database.execute(
            'INSERT INTO study_groups (name) VALUES (?)',
            (name,)
        )

        group_id = result.lastrowid
        group = await database.fetch_one(
            'SELECT id, name, created_at FROM study_groups WHERE id = ?',
            (group_id,)
        )

        return StudyGroup(id=group[0], name=group[1], created_at=group[2])

    async def update_group(self, group_id: int, new_name: str) -> StudyGroup:
        """Переименовать группу"""
        # Проверяем существование группы
        existing = await database.fetch_one(
            'SELECT id FROM study_groups WHERE id = ?',
            (group_id,)
        )
        if not existing:
            raise ValueError("Группа не найдена")

        # Проверяем уникальность нового имени
        name_exists = await database.fetch_one(
            'SELECT id FROM study_groups WHERE name = ? AND id != ?',
            (new_name, group_id)
        )
        if name_exists:
            raise ValueError(f"Группа с именем '{new_name}' уже существует")

        # Обновляем имя
        await database.execute(
            'UPDATE study_groups SET name = ? WHERE id = ?',
            (new_name, group_id)
        )

        group = await database.fetch_one(
            'SELECT id, name, created_at FROM study_groups WHERE id = ?',
            (group_id,)
        )

        return StudyGroup(id=group[0], name=group[1], created_at=group[2])

    async def delete_group(self, group_id: int) -> bool:
        """Удалить группу и все её данные"""
        if group_id == 1:
            raise ValueError("Нельзя удалить основную группу")

        try:
            print(f"🗑️ Удаление группы {group_id} и всех её данных...")

            # 1. Проверяем существование группы
            group_exists = await database.fetch_one(
                'SELECT id FROM study_groups WHERE id = ?',
                (group_id,)
            )
            if not group_exists:
                print(f"❌ Группа {group_id} не найдена")
                return False

            # 2. Удаляем данные группы из всех таблиц
            tables_to_clean = [
                'subjects',  # Предметы группы
                'lessons',  # Расписание группы
                'saved_schedules'  # Сохраненные расписания группы
            ]

            for table in tables_to_clean:
                try:
                    result = await database.execute(
                        f'DELETE FROM {table} WHERE group_id = ?',
                        (group_id,)
                    )
                    print(f"🧹 Удалено из {table}: {result.rowcount} записей")
                except Exception as e:
                    print(f"⚠️ Ошибка при очистке {table}: {e}")

            # 3. Удаляем саму группу
            result = await database.execute(
                'DELETE FROM study_groups WHERE id = ?',
                (group_id,)
            )

            if result.rowcount > 0:
                print(f"✅ Группа {group_id} успешно удалена")
                return True
            else:
                print(f"❌ Не удалось удалить группу {group_id}")
                return False

        except Exception as e:
            print(f"❌ Ошибка удаления группы {group_id}: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            raise ValueError(f"Ошибка удаления группы: {str(e)}")

    async def group_exists(self, group_id: int) -> bool:
        """Проверить существование группы"""
        row = await database.fetch_one(
            'SELECT id FROM study_groups WHERE id = ?',
            (group_id,)
        )
        return row is not None


# Глобальный экземпляр
group_service = GroupService()