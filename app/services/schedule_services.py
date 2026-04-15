# app/services/schedule_services.py
from app.db.database import database
from app.db.models import Lesson
from typing import List
from app.services.shedule_generator import schedule_generator


class ScheduleService:
    def __init__(self):
        self.generator = schedule_generator

    async def generate_schedule(self, group_id: int = 1) -> List[Lesson]:
        """Просто используем главный генератор"""
        return await self.generator.generate_schedule(group_id)

    async def get_all_lessons(self, group_id: int = 1) -> List[Lesson]:
        """Получить все уроки группы"""
        rows = await database.fetch_all(
            'SELECT id, day, time_slot, teacher, subject_name, editable FROM lessons WHERE group_id = ? ORDER BY day, time_slot',
            (group_id,)
        )
        return [
            Lesson(
                id=row[0],
                day=row[1],
                time_slot=row[2],
                teacher=row[3],
                subject_name=row[4],
                editable=bool(row[5])
            )
            for row in rows
        ]

    async def remove_lesson(self, day: int, time_slot: int, group_id: int = 1) -> bool:
        """Удалить урок"""
        try:
            # Получаем удаляемый урок
            lesson = await database.fetch_one(
                'SELECT teacher, subject_name FROM lessons WHERE day = ? AND time_slot = ? AND group_id = ?',
                (day, time_slot, group_id)
            )

            if not lesson:
                return False

            teacher, subject_name = lesson

            # Восстанавливаем часы
            subject = await database.fetch_one(
                'SELECT id FROM subjects WHERE teacher = ? AND subject_name = ? AND group_id = ?',
                (teacher, subject_name, group_id)
            )

            if subject:
                subject_id = subject[0]
                # Восстанавливаем 2 часа
                await database.execute(
                    '''UPDATE subjects 
                       SET remaining_hours = remaining_hours + 2,
                           remaining_pairs = (remaining_hours + 2) / 2
                       WHERE id = ?''',
                    (subject_id,)
                )

            # Удаляем урок
            result = await database.execute(
                'DELETE FROM lessons WHERE day = ? AND time_slot = ? AND group_id = ?',
                (day, time_slot, group_id)
            )

            return result.rowcount > 0

        except Exception as e:
            print(f"❌ Ошибка удаления урока: {e}")
            return False

    async def get_statistics(self, group_id: int = 1):
        """Получить статистику"""
        try:
            subjects_count = await database.fetch_one(
                'SELECT COUNT(*) FROM subjects WHERE group_id = ?',
                (group_id,)
            )

            teachers_count = await database.fetch_one(
                'SELECT COUNT(DISTINCT teacher) FROM subjects WHERE group_id = ?',
                (group_id,)
            )

            hours_data = await database.fetch_one(
                'SELECT SUM(total_hours), SUM(remaining_hours) FROM subjects WHERE group_id = ?',
                (group_id,)
            )

            pairs_data = await database.fetch_one(
                'SELECT COUNT(*) FROM lessons WHERE group_id = ?',
                (group_id,)
            )

            total_hours = hours_data[0] or 0
            remaining_hours = hours_data[1] or 0
            scheduled_pairs = pairs_data[0] or 0
            remaining_pairs = (remaining_hours // 2) if remaining_hours else 0

            return {
                "total_subjects": subjects_count[0] or 0,
                "total_teachers": teachers_count[0] or 0,
                "total_hours": total_hours,
                "remaining_hours": remaining_hours,
                "scheduled_pairs": scheduled_pairs,
                "remaining_pairs": remaining_pairs
            }
        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
            return {
                "total_subjects": 0,
                "total_teachers": 0,
                "total_hours": 0,
                "remaining_hours": 0,
                "scheduled_pairs": 0,
                "remaining_pairs": 0
            }


# Глобальный экземпляр
schedule_service = ScheduleService()