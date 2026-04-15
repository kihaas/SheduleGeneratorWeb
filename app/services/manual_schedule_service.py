from app.db.database import database
from app.services.negative_filters_service import negative_filters_service
from app.services.subject_services import subject_service
from typing import Dict, Optional, Tuple
import json


class ManualScheduleService:
    """Сервис для ручного управления расписанием"""

    async def check_teacher_availability(self, teacher: str, day: int,
                                         time_slot: int, current_group_id: int) -> Tuple[bool, str]:
        """Проверить доступность преподавателя"""
        try:
            # 1. Проверяем, не ведет ли преподаватель в это время в другой группе
            conflict = await database.fetch_one(
                '''SELECT group_id FROM lessons 
                   WHERE teacher = ? AND day = ? AND time_slot = ? AND group_id != ?''',
                (teacher, day, time_slot, current_group_id)
            )

            if conflict:
                other_group_id = conflict[0]
                return False, f"Преподаватель уже ведет занятие в группе {other_group_id} в это время"

            # 2. Проверяем ограничения преподавателя (negative_filters)
            filters = await negative_filters_service.get_teacher_filters(teacher)
            if filters:
                if day in filters.get('restricted_days', []):
                    return False, f"Преподаватель недоступен в этот день недели"

                if time_slot in filters.get('restricted_slots', []):
                    return False, f"Преподаватель недоступен в эту пару"

            # 3. Проверяем, что слот свободен в текущей группе
            slot_occupied = await database.fetch_one(
                'SELECT id FROM lessons WHERE day = ? AND time_slot = ? AND group_id = ?',
                (day, time_slot, current_group_id)
            )
            if slot_occupied:
                return False, "Эта ячейка уже занята"

            return True, "Преподаватель доступен"

        except Exception as e:
            return False, f"Ошибка проверки доступности: {str(e)}"

    async def check_subject_availability(self, teacher: str, subject_name: str,
                                         day: int, group_id: int) -> Tuple[bool, str, Optional[int]]:
        """Проверить доступность предмета для добавления"""
        try:
            # 1. Проверяем, существует ли предмет в группе
            subject = await subject_service.get_subject_by_name(teacher, subject_name, group_id)
            if not subject:
                return False, f"Предмет '{subject_name}' не найден у преподавателя {teacher} в этой группе", None

            # 2. Проверяем, остались ли пары у предмета
            if subject.remaining_pairs <= 0:
                return False, f"У предмета '{subject_name}' не осталось пар для распределения", None

            # 3. Проверяем max_per_day (если сегодня уже есть пары этого предмета)
            today_pairs = await database.fetch_one(
                '''SELECT COUNT(*) FROM lessons 
                   WHERE teacher = ? AND subject_name = ? AND day = ? AND group_id = ?''',
                (teacher, subject_name, day, group_id)  # Используем переданный day
            )

            today_count = today_pairs[0] if today_pairs else 0
            if today_count >= subject.max_per_day:
                return False, f"Превышен лимит {subject.max_per_day} пар в день для этого предмета", None

            return True, "Предмет доступен", subject.id

        except Exception as e:
            return False, f"Ошибка проверки предмета: {str(e)}", None

    async def add_lesson(self, day: int, time_slot: int, teacher: str,
                         subject_name: str, group_id: int) -> Dict:
        """Добавить пару вручную"""
        try:
            print(f"➕ Ручное добавление пары: день={day}, слот={time_slot}, "
                  f"преподаватель={teacher}, предмет={subject_name}, группа={group_id}")

            # 1. Проверяем доступность преподавателя
            teacher_ok, teacher_msg = await self.check_teacher_availability(
                teacher, day, time_slot, group_id
            )
            if not teacher_ok:
                return {"success": False, "message": teacher_msg}

            # 2. Проверяем доступность предмета (передаем day)
            subject_ok, subject_msg, subject_id = await self.check_subject_availability(
                teacher, subject_name, day, group_id  # Передаем day
            )
            if not subject_ok:
                return {"success": False, "message": subject_msg}

            # 3. Проверяем, не занят ли уже этот слот в этой группе
            existing_lesson = await database.fetch_one(
                'SELECT id FROM lessons WHERE day = ? AND time_slot = ? AND group_id = ?',
                (day, time_slot, group_id)
            )
            if existing_lesson:
                return {"success": False, "message": "Этот слот уже занят в текущей группе"}

            # 4. Добавляем урок
            result = await database.execute(
                '''INSERT INTO lessons (day, time_slot, teacher, subject_name, editable, group_id)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (day, time_slot, teacher, subject_name, 1, group_id)
            )

            if result.rowcount == 0:
                return {"success": False, "message": "Не удалось добавить пару"}

            # 5. Обновляем оставшиеся часы у предмета
            await database.execute(
                '''UPDATE subjects 
                   SET remaining_hours = remaining_hours - 2,
                       remaining_pairs = (remaining_hours - 2) / 2
                   WHERE id = ?''',
                (subject_id,)
            )

            return {
                "success": True,
                "message": "Пара успешно добавлена",
                "lesson_id": result.lastrowid
            }

        except Exception as e:
            print(f"❌ Ошибка ручного добавления пары: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return {"success": False, "message": f"Внутренняя ошибка: {str(e)}"}

    async def update_lesson(self, day: int, time_slot: int, new_teacher: str,
                            new_subject_name: str, group_id: int) -> Dict:
        """Обновить существующую пару (аналог существующей функции)"""
        try:
            print(f"✏️ Ручное обновление пары: день={day}, слот={time_slot}, "
                  f"новый преподаватель={new_teacher}, новый предмет={new_subject_name}")

            # 1. Получаем старый урок ДО проверок
            old_lesson = await database.fetch_one(
                'SELECT teacher, subject_name FROM lessons WHERE day = ? AND time_slot = ? AND group_id = ?',
                (day, time_slot, group_id)
            )

            # Если пытаемся заменить на ТОГО ЖЕ преподавателя и предмет - ничего не делаем
            if old_lesson:
                old_teacher, old_subject_name = old_lesson
                if old_teacher == new_teacher and old_subject_name == new_subject_name:
                    return {"success": True, "message": "Изменений не требуется"}

            # 2. Проверяем доступность нового преподавателя (с исключением САМОГО СЕБЯ)
            teacher_ok, teacher_msg = await self.check_teacher_availability_with_exception(
                new_teacher, day, time_slot, group_id, old_teacher if old_lesson else None
            )
            if not teacher_ok:
                return {"success": False, "message": teacher_msg}

            # 3. Проверяем доступность нового предмета
            subject_ok, subject_msg, new_subject_id = await self.check_subject_availability(
                new_teacher, new_subject_name, day, group_id
            )
            if not subject_ok:
                return {"success": False, "message": subject_msg}

            # 4. Если урока нет - создаем новый
            if not old_lesson:
                return await self.add_lesson(day, time_slot, new_teacher, new_subject_name, group_id)

            # 5. Восстанавливаем часы старого предмета
            old_subject = await subject_service.get_subject_by_name(
                old_teacher, old_subject_name, group_id
            )
            if old_subject:
                await database.execute(
                    '''UPDATE subjects 
                       SET remaining_hours = remaining_hours + 2,
                           remaining_pairs = remaining_hours / 2
                       WHERE id = ?''',
                    (old_subject.id,)
                )
                print(f"✅ Восстановлено 2 часа для старого предмета: {old_subject_name}")

            # 6. Вычитаем часы нового предмета
            await database.execute(
                '''UPDATE subjects 
                   SET remaining_hours = remaining_hours - 2,
                       remaining_pairs = remaining_hours / 2
                   WHERE id = ?''',
                (new_subject_id,)
            )
            print(f"✅ Вычтено 2 часа для нового предмета: {new_subject_name}")

            # 7. Обновляем урок
            result = await database.execute(
                '''UPDATE lessons 
                   SET teacher = ?, subject_name = ?, editable = 1
                   WHERE day = ? AND time_slot = ? AND group_id = ?''',
                (new_teacher, new_subject_name, day, time_slot, group_id)
            )

            if result.rowcount == 0:
                return {"success": False, "message": "Не удалось обновить урок"}

            return {
                "success": True,
                "message": "Пара успешно обновлена"
            }

        except Exception as e:
            print(f"❌ Ошибка ручного обновления пары: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return {"success": False, "message": f"Ошибка обновления: {str(e)}"}

    # ДОБАВЛЯЕМ НОВЫЙ МЕТОД ДЛЯ ПРОВЕРКИ С ИСКЛЮЧЕНИЕМ
    async def check_teacher_availability_with_exception(self, teacher: str, day: int,
                                                        time_slot: int, current_group_id: int,
                                                        except_teacher: str = None) -> Tuple[bool, str]:
        """Проверить доступность преподавателя с исключением (для замены)"""
        try:
            # 1. Проверяем, не ведет ли преподаватель в это время в другой группе
            conflict = await database.fetch_one(
                '''SELECT group_id FROM lessons 
                   WHERE teacher = ? AND day = ? AND time_slot = ? AND group_id != ?''',
                (teacher, day, time_slot, current_group_id)
            )

            if conflict:
                other_group_id = conflict[0]
                return False, f"Преподаватель уже ведет занятие в группе {other_group_id} в это время"

            # 2. Если это ЗАМЕНА того же преподавателя - разрешаем
            if except_teacher and teacher == except_teacher:
                print(f"⚠️ Разрешаем замену того же преподавателя: {teacher}")
                # Пропускаем проверку занятости в текущей группе
            else:
                # 3. Проверяем, не занят ли преподаватель в ТЕКУЩЕЙ группе в это время
                # (но это должен быть ДРУГОЙ урок, не тот который заменяем)
                conflict_in_current = await database.fetch_one(
                    '''SELECT teacher FROM lessons 
                       WHERE teacher = ? AND day = ? AND time_slot = ? AND group_id = ?''',
                    (teacher, day, time_slot, current_group_id)
                )

                if conflict_in_current and conflict_in_current[0] != except_teacher:
                    return False, f"Преподаватель уже ведет другой урок в это время в текущей группе"

            # 4. Проверяем ограничения преподавателя (negative_filters)
            filters = await negative_filters_service.get_teacher_filters(teacher)
            if filters:
                if day in filters.get('restricted_days', []):
                    return False, f"Преподаватель недоступен в этот день недели"

                if time_slot in filters.get('restricted_slots', []):
                    return False, f"Преподаватель недоступен в эту пару"

            return True, "Преподаватель доступен"

        except Exception as e:
            return False, f"Ошибка проверки доступности: {str(e)}"


    async def delete_lesson(self, day: int, time_slot: int, group_id: int) -> Dict:
        """Удалить пару вручную"""
        try:
            print(f"🗑️ Удаление пары: день={day}, слот={time_slot}, группа={group_id}")

            # 1. Получаем удаляемый урок
            lesson = await database.fetch_one(
                'SELECT teacher, subject_name FROM lessons WHERE day = ? AND time_slot = ? AND group_id = ?',
                (day, time_slot, group_id)
            )

            if not lesson:
                return {"success": False, "message": "Урок не найден"}

            teacher, subject_name = lesson

            # 2. Восстанавливаем часы предмета
            subject = await subject_service.get_subject_by_name(teacher, subject_name, group_id)
            if subject:
                await database.execute(
                    '''UPDATE subjects 
                       SET remaining_hours = remaining_hours + 2,
                           remaining_pairs = (remaining_hours + 2) / 2
                       WHERE id = ?''',
                    (subject.id,)
                )
                print(f"✅ Восстановлено 2 часа для предмета {subject_name}")

            # 3. Удаляем урок
            result = await database.execute(
                'DELETE FROM lessons WHERE day = ? AND time_slot = ? AND group_id = ?',
                (day, time_slot, group_id)
            )

            if result.rowcount == 0:
                return {"success": False, "message": "Не удалось удалить урок"}

            return {
                "success": True,
                "message": "Пара успешно удалена"
            }

        except Exception as e:
            print(f"❌ Ошибка удаления пары: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return {"success": False, "message": f"Ошибка удаления: {str(e)}"}


# Глобальный экземпляр
manual_schedule_service = ManualScheduleService()