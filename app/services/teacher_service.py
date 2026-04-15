from app.db.database import database
from app.db.models import Teacher
from typing import List, Optional


class TeacherService:
    async def create_teacher(self, name: str) -> Teacher:
        """Создать преподавателя (ГЛОБАЛЬНО - для всех групп)"""
        # Проверяем существование преподавателя (глобально)
        existing = await database.fetch_one(
            'SELECT id FROM teachers WHERE name = ?',
            (name,)
        )
        if existing:
            raise ValueError("Преподаватель с таким именем уже существует")

        result = await database.execute(
            'INSERT INTO teachers (name) VALUES (?)',
            (name,)
        )

        teacher = await database.fetch_one(
            'SELECT id, name, created_at FROM teachers WHERE id = ?',
            (result.lastrowid,)
        )

        return Teacher(id=teacher[0], name=teacher[1], created_at=teacher[2])

    async def get_all_teachers(self) -> List[Teacher]:
        """Получить всех преподавателей (ГЛОБАЛЬНО - для всех групп)"""
        rows = await database.fetch_all(
            'SELECT id, name, created_at FROM teachers ORDER BY name'
        )
        return [
            Teacher(id=row[0], name=row[1], created_at=row[2])
            for row in rows
        ]

    async def get_teacher(self, teacher_id: int) -> Optional[Teacher]:
        """Получить преподавателя по ID"""
        row = await database.fetch_one(
            'SELECT id, name, created_at FROM teachers WHERE id = ?',
            (teacher_id,)
        )
        if row:
            return Teacher(id=row[0], name=row[1], created_at=row[2])
        return None

    async def get_teacher_by_name(self, name: str) -> Optional[Teacher]:
        """Получить преподавателя по имени (ГЛОБАЛЬНО)"""
        row = await database.fetch_one(
            'SELECT id, name, created_at FROM teachers WHERE name = ?',
            (name,)
        )
        if row:
            return Teacher(id=row[0], name=row[1], created_at=row[2])
        return None

    async def update_teacher(self, teacher_id: int, name: str) -> Optional[Teacher]:
        """Обновить преподавателя"""
        result = await database.execute(
            'UPDATE teachers SET name = ? WHERE id = ?',
            (name, teacher_id)
        )

        if result.rowcount > 0:
            return await self.get_teacher(teacher_id)
        return None

    async def delete_teacher(self, teacher_id: int) -> bool:
        """Удалить преподавателя (ГЛОБАЛЬНО - из всех групп)"""
        result = await database.execute(
            'DELETE FROM teachers WHERE id = ?',
            (teacher_id,)
        )
        return result.rowcount > 0

    async def teacher_exists(self, teacher_id: int) -> bool:
        """Проверить существование преподавателя"""
        row = await database.fetch_one(
            'SELECT id FROM teachers WHERE id = ?',
            (teacher_id,)
        )
        return row is not None

    async def get_teachers_for_group(self, group_id: int) -> List[Teacher]:
        """Получить преподавателей, которые ведут предметы в указанной группе"""
        rows = await database.fetch_all('''
            SELECT DISTINCT t.id, t.name, t.created_at 
            FROM teachers t
            JOIN subjects s ON t.name = s.teacher
            WHERE s.group_id = ?
            ORDER BY t.name
        ''', (group_id,))

        return [
            Teacher(id=row[0], name=row[1], created_at=row[2])
            for row in rows
        ]


# Глобальный экземпляр
teacher_service = TeacherService()