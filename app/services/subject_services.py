from app.db.database import database
from app.db.models import Subject
from typing import List, Optional
import json


# app/services/subject_services.py
class SubjectService:
    async def create_subject(self, teacher: str, subject_name: str, hours: int,
                             priority: int = 0, max_per_day: int = 2,
                             group_id: int = 1,
                             min_per_week: int = 1, max_per_week: int = 20) -> Subject:
        """Создать предмет с недельными квотами"""
        print(f"🔄 Создание предмета: {teacher} - {subject_name} в группе {group_id}")

        # Сначала проверим что преподаватель существует
        teacher_exists = await database.fetch_one(
            'SELECT id FROM teachers WHERE name = ?',
            (teacher,)
        )
        if not teacher_exists:
            raise ValueError(f"Преподаватель '{teacher}' не существует. Сначала создайте преподавателя.")

        # Теперь проверяем существование предмета в этой группе
        existing = await database.fetch_one(
            'SELECT id FROM subjects WHERE teacher = ? AND subject_name = ? AND group_id = ?',
            (teacher, subject_name, group_id)
        )

        print(f"🔍 Проверка существования: teacher={teacher}, subject={subject_name}, group={group_id}")
        print(f"🔍 Результат проверки: {'НАЙДЕН' if existing else 'НЕ НАЙДЕН'}")

        if existing:
            raise ValueError("Предмет с таким названием уже существует у этого преподавателя в этой группе")

        # Валидация недельных квот
        if min_per_week < 0:
            min_per_week = 0
        if max_per_week > 20:  # Увеличили максимум до 20
            max_per_week = 20
        if min_per_week > max_per_week:
            min_per_week, max_per_week = max_per_week, min_per_week

        # Рассчитываем пары (1 пара = 2 часа)
        remaining_pairs = hours // 2
        print(f"📊 Часы: {hours}, пар: {remaining_pairs}")

        try:
            result = await database.execute(
                '''INSERT INTO subjects 
                   (teacher, subject_name, total_hours, remaining_hours, remaining_pairs, 
                    priority, max_per_day, group_id,
                    min_per_week, max_per_week) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',  # Убрали weeks_in_semester
                (teacher, subject_name, hours, hours, remaining_pairs,
                 priority, max_per_day, group_id,
                 min_per_week, max_per_week)
            )

            subject_id = result.lastrowid
            print(f"✅ Предмет создан с ID: {subject_id}")

            subject = await database.fetch_one(
                '''SELECT id, teacher, subject_name, total_hours, remaining_hours, 
                          remaining_pairs, priority, max_per_day,
                          min_per_week, max_per_week
                   FROM subjects WHERE id = ?''',
                (subject_id,)
            )

            return Subject(
                id=subject[0],
                teacher=subject[1],
                subject_name=subject[2],
                total_hours=subject[3],
                remaining_hours=subject[4],
                remaining_pairs=subject[5],
                priority=subject[6],
                max_per_day=subject[7],
                min_per_week=subject[8],
                max_per_week=subject[9]
            )

        except Exception as e:
            print(f"❌ Ошибка при вставке в БД: {e}")
            raise

    async def get_all_subjects(self, group_id: int = 1) -> List[Subject]:
        """Получить все предметы группы"""
        print(f"🔍 Загрузка предметов для группы {group_id}")

        rows = await database.fetch_all(
            '''SELECT id, teacher, subject_name, total_hours, remaining_hours, 
                      remaining_pairs, priority, max_per_day,
                      min_per_week, max_per_week
               FROM subjects WHERE group_id = ? ORDER BY subject_name''',
            (group_id,)
        )

        print(f"📊 Загружено предметов: {len(rows)}")
        return [
            Subject(
                id=row[0],
                teacher=row[1],
                subject_name=row[2],
                total_hours=row[3],
                remaining_hours=row[4],
                remaining_pairs=row[5],
                priority=row[6],
                max_per_day=row[7],
                min_per_week=row[8],
                max_per_week=row[9]
            )
            for row in rows
        ]

    async def get_all_subjects(self, group_id: int = 1) -> List[Subject]:
        """Получить все предметы группы"""
        try:
            print(f"📚 Загрузка предметов для группы {group_id}")

            rows = await database.fetch_all(
                '''SELECT id, teacher, subject_name, total_hours, remaining_hours, 
                          remaining_pairs, priority, max_per_day, 
                          min_per_week, max_per_week
                   FROM subjects WHERE group_id = ? ORDER BY subject_name''',
                (group_id,)
            )

            print(f"✅ Найдено предметов: {len(rows)}")

            subjects = []
            for row in rows:
                subjects.append(Subject(
                    id=row[0],
                    teacher=row[1],
                    subject_name=row[2],
                    total_hours=row[3],
                    remaining_hours=row[4],
                    remaining_pairs=row[5],
                    priority=row[6],
                    max_per_day=row[7],
                    min_per_week=row[8],
                    max_per_week=row[9]
                ))

            return subjects

        except Exception as e:
            print(f"❌ Ошибка загрузки предметов: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
            return []  # Возвращаем пустой список вместо ошибки

    async def get_subject_by_name(self, teacher: str, subject_name: str, group_id: int = 1) -> Optional[Subject]:
        """Получить предмет по имени преподавателя и названию в группе"""
        try:
            row = await database.fetch_one(
                '''SELECT id, teacher, subject_name, total_hours, remaining_hours,
                          remaining_pairs, priority, max_per_day,
                          min_per_week, max_per_week
                   FROM subjects
                   WHERE teacher = ? AND subject_name = ? AND group_id = ?''',
                (teacher, subject_name, group_id)  # ✅ КОРРЕКТНЫЙ СИНТАКСИС
            )

            if row:
                return Subject(
                    id=row[0],
                    teacher=row[1],
                    subject_name=row[2],
                    total_hours=row[3],
                    remaining_hours=row[4],
                    remaining_pairs=row[5],
                    priority=row[6],
                    max_per_day=row[7],
                    min_per_week=row[8],
                    max_per_week=row[9]
                )
            return None

        except Exception as e:
            print(f"❌ Ошибка в get_subject_by_name: {e}")
            return None


    async def delete_subject(self, subject_id: int) -> bool:
        """Удалить предмет"""
        result = await database.execute(
            'DELETE FROM subjects WHERE id = ?',
            (subject_id,)
        )
        return result.rowcount > 0

    async def get_negative_filters(self, group_id=None):  # Добавляем необязательный параметр
        """Получить ГЛОБАЛЬНЫЕ ограничения"""
        try:
            # Игнорируем group_id если передан, но используем глобальные фильтры
            if group_id is not None:
                print(f"⚠️  Внимание: get_negative_filters вызван с group_id={group_id}, но фильтры глобальные")

            rows = await database.fetch_all(
                'SELECT teacher, restricted_days, restricted_slots FROM negative_filters'
            )

            filters = {}
            for row in rows:
                teacher, days_json, slots_json = row
                try:
                    filters[teacher] = {
                        "restricted_days": json.loads(days_json) if days_json else [],
                        "restricted_slots": json.loads(slots_json) if slots_json else []
                    }
                except:
                    filters[teacher] = {
                        "restricted_days": [],
                        "restricted_slots": []
                    }

            return filters
        except Exception as e:
            print(f"❌ Ошибка получения глобальных фильтров: {e}")
            return {}

    async def update_subject_hours(self, subject_id: int, delta_hours: int) -> bool:
        """Обновить оставшиеся часы предмета (дельта может быть положительной или отрицательной)"""
        try:
            print(f"🔄 Обновление часов предмета {subject_id}: delta={delta_hours}")

            # СНАЧАЛА получаем текущие значения
            subject = await database.fetch_one(
                'SELECT remaining_hours, total_hours FROM subjects WHERE id = ?',
                (subject_id,)
            )

            if not subject:
                print(f"❌ Предмет {subject_id} не найден")
                return False

            current_hours = subject[0]
            total_hours = subject[1]

            # Вычисляем новые значения
            new_hours = current_hours - delta_hours  # delta_hours положительный = заняли пару

            # Проверяем границы
            if new_hours < 0:
                new_hours = 0
            if new_hours > total_hours:
                new_hours = total_hours

            # Вычисляем пары (1 пара = 2 часа)
            new_pairs = new_hours // 2

            print(f"📊 Текущие: {current_hours}ч, Новые: {new_hours}ч, Пар: {new_pairs}")

            # Обновляем БД
            result = await database.execute(
                '''UPDATE subjects 
                   SET remaining_hours = ?,
                       remaining_pairs = ?
                   WHERE id = ?''',
                (new_hours, new_pairs, subject_id)
            )

            if result.rowcount > 0:
                print(f"✅ Часы обновлены: {new_hours}ч, {new_pairs} пар")
                return True
            return False
        except Exception as e:
            print(f"❌ Ошибка обновления часов предмета {subject_id}: {e}")
            return False


# Глобальный экземпляр
subject_service = SubjectService()