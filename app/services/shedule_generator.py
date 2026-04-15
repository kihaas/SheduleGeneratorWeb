# app/services/schedule_generator.py
from typing import List, Dict, Tuple
import random
from collections import defaultdict
import math

from app.db.database import database
from app.db.models import Lesson, Subject
from app.services.subject_services import subject_service
from app.services.negative_filters_service import negative_filters_service


class ScheduleGenerator:
    """Улучшенный генератор расписания с учетом ВСЕХ параметров"""

    def __init__(self):
        self.occupied_slots = set()

    async def generate_schedule(self, group_id: int = 1) -> List[Lesson]:
        """Главный метод генерации расписания"""
        print(f"🎯 Генерация расписания для группы {group_id}...")

        # Получаем предметы
        subjects = await subject_service.get_all_subjects(group_id)
        print(f"📚 Найдено предметов: {len(subjects)}")

        if not subjects:
            print("❌ Нет предметов для генерации")
            return []

        # Получаем фильтры
        negative_filters = await negative_filters_service.get_negative_filters()

        # Очищаем старое расписание и восстанавливаем часы
        await self.clear_and_reset(group_id)

        # Генерируем расписание
        lessons = await self.generate_with_all_params(subjects, negative_filters, group_id)

        # Сохраняем уроки
        for lesson in lessons:
            await database.execute(
                'INSERT INTO lessons (day, time_slot, teacher, subject_name, editable, group_id) VALUES (?, ?, ?, ?, ?, ?)',
                (lesson.day, lesson.time_slot, lesson.teacher, lesson.subject_name, int(lesson.editable), group_id)
            )

        # Обновляем часы
        await self.update_hours_after_generation(lessons, group_id)

        print(f"✅ Сгенерировано {len(lessons)} уроков (максимум 20)")
        return lessons

    async def clear_and_reset(self, group_id: int):
        """Очистить расписание и восстановить часы"""
        # Удаляем старые уроки
        await database.execute(
            'DELETE FROM lessons WHERE group_id = ?',
            (group_id,)
        )

        # Восстанавливаем все часы
        await database.execute(
            '''UPDATE subjects 
               SET remaining_hours = total_hours,
                   remaining_pairs = total_hours / 2 
               WHERE group_id = ?''',
            (group_id,)
        )

    async def generate_with_all_params(self, subjects: List[Subject], negative_filters: Dict, group_id: int = 1) -> \
    List[Lesson]:
        """Генерация с учетом ВСЕХ параметров"""
        print(f"⚡ Генерация с квотами для {len(subjects)} предметов")

        # 1. Подготавливаем предметы
        subject_info = self._prepare_subject_info(subjects)

        # 2. Рассчитываем, сколько пар нужно распределить
        subject_distribution = self._calculate_distribution(subject_info)

        print(f"📊 Распределение пар: {subject_distribution}")
        total_pairs_needed = sum(info['pairs_to_assign'] for info in subject_distribution.values())
        print(f"📊 Всего пар для распределения: {total_pairs_needed}")

        # 3. Создаем пустое расписание на неделю (5 дней × 4 пары = 20 слотов)
        week_schedule = self._create_empty_schedule()

        # 4. Распределяем пары по расписанию
        lessons = await self._fill_schedule(
            subject_distribution, subject_info, negative_filters,
            group_id, week_schedule
        )

        return lessons

    def _prepare_subject_info(self, subjects: List[Subject]) -> Dict:
        """Подготовить информацию о предметах"""
        subject_info = {}

        for subject in subjects:
            key = (subject.teacher, subject.subject_name)
            subject_info[key] = {
                'id': subject.id,
                'priority': subject.priority,
                'max_per_day': subject.max_per_day,
                'min_per_week': getattr(subject, 'min_per_week', 0),
                'max_per_week': getattr(subject, 'max_per_week', 20),
                'total_pairs_needed': subject.remaining_pairs,
                'remaining_pairs': subject.remaining_pairs
            }

        return subject_info

    def _calculate_distribution(self, subject_info: Dict) -> Dict:
        """Рассчитать распределение пар по предметам с учетом квот"""
        distribution = {}

        for (teacher, subject_name), info in subject_info.items():
            min_pairs = info['min_per_week']
            max_pairs = info['max_per_week']
            needed_pairs = info['total_pairs_needed']

            # Определяем сколько пар поставить
            if min_pairs > 0:
                # Гарантируем минимум
                pairs_to_assign = max(min_pairs, min(needed_pairs, max_pairs))
            else:
                # Без гарантии, но с ограничением максимума
                pairs_to_assign = min(needed_pairs, max_pairs)

            if pairs_to_assign > 0:
                distribution[(teacher, subject_name)] = {
                    'pairs_to_assign': pairs_to_assign,
                    'max_per_day': info['max_per_day'],
                    'priority': info['priority']
                }

        # Сортируем по приоритету (высокий приоритет сначала)
        sorted_distribution = dict(sorted(
            distribution.items(),
            key=lambda x: x[1]['priority'],
            reverse=True
        ))

        return sorted_distribution

    def _create_empty_schedule(self) -> Dict[Tuple[int, int], bool]:
        """Создать пустое расписание на неделю"""
        week_schedule = {}
        for day in range(5):  # Пн-Пт
            for time_slot in range(4):  # 4 пары в день
                week_schedule[(day, time_slot)] = False  # False = свободно
        return week_schedule

    async def _fill_schedule(self, subject_distribution: Dict, subject_info: Dict,
                             negative_filters: Dict, group_id: int,
                             week_schedule: Dict) -> List[Lesson]:
        """Заполнить расписание парами"""
        lessons = []

        # Создаем список всех слотов
        all_slots = list(week_schedule.keys())
        random.shuffle(all_slots)  # Перемешиваем слоты

        # Создаем список всех пар для распределения
        all_pairs_to_place = []
        for (teacher, subject_name), info in subject_distribution.items():
            for _ in range(info['pairs_to_assign']):
                all_pairs_to_place.append({
                    'teacher': teacher,
                    'subject_name': subject_name,
                    'max_per_day': info['max_per_day'],
                    'priority': info['priority']
                })

        # Перемешиваем пары для лучшего распределения
        random.shuffle(all_pairs_to_place)

        # Счетчики для контроля max_per_day
        daily_counts = defaultdict(lambda: defaultdict(int))  # day -> (teacher, subject) -> count

        # Пытаемся разместить каждую пару
        for pair_info in all_pairs_to_place:
            teacher = pair_info['teacher']
            subject_name = pair_info['subject_name']
            max_per_day = pair_info['max_per_day']

            placed = False

            # Пробуем разместить в случайном порядке слотов
            for day, time_slot in all_slots:
                # Проверяем свободен ли слот
                if week_schedule[(day, time_slot)]:
                    continue

                # Проверяем max_per_day
                key = (teacher, subject_name)
                if daily_counts[day][key] >= max_per_day:
                    continue

                # Проверяем доступность преподавателя
                if not self._is_teacher_available(teacher, day, time_slot, negative_filters):
                    continue

                # Проверяем что преподаватель не занят в других группах
                if not await self._is_teacher_free_across_groups(teacher, day, time_slot, group_id):
                    continue

                # Нашли подходящий слот - размещаем
                lesson = Lesson(
                    day=day,
                    time_slot=time_slot,
                    teacher=teacher,
                    subject_name=subject_name,
                    editable=True
                )
                lessons.append(lesson)
                week_schedule[(day, time_slot)] = True  # Помечаем как занятый
                daily_counts[day][key] += 1
                placed = True
                break

            if not placed:
                # Пробуем найти слот без проверки конфликтов между группами (как крайний вариант)
                for day, time_slot in all_slots:
                    if week_schedule[(day, time_slot)]:
                        continue

                    if daily_counts[day][(teacher, subject_name)] >= max_per_day:
                        continue

                    if not self._is_teacher_available(teacher, day, time_slot, negative_filters):
                        continue

                    # Размещаем даже если есть конфликт в других группах
                    lesson = Lesson(
                        day=day,
                        time_slot=time_slot,
                        teacher=teacher,
                        subject_name=subject_name,
                        editable=True
                    )
                    lessons.append(lesson)
                    week_schedule[(day, time_slot)] = True
                    daily_counts[day][(teacher, subject_name)] += 1
                    print(
                        f"⚠️ Размещено с возможным конфликтом: {teacher} - {subject_name} в день {day}, слот {time_slot}")
                    placed = True
                    break

            if not placed:
                print(f"❌ Не удалось разместить {teacher} - {subject_name}")

        # Статистика распределения
        occupied_count = sum(1 for occupied in week_schedule.values() if occupied)
        print(f"📊 Занято слотов: {occupied_count}/20")

        return lessons

    def _is_teacher_available(self, teacher: str, day: int, time_slot: int, negative_filters: Dict) -> bool:
        """Проверить доступность преподавателя"""
        if teacher not in negative_filters:
            return True

        filters = negative_filters[teacher]

        if day in filters.get('restricted_days', []):
            return False

        if time_slot in filters.get('restricted_slots', []):
            return False

        return True

    async def _is_teacher_free_across_groups(self, teacher: str, day: int, time_slot: int,
                                             current_group_id: int) -> bool:
        """Проверить что преподаватель свободен в других группах"""
        try:
            existing = await database.fetch_one(
                'SELECT id FROM lessons WHERE teacher = ? AND day = ? AND time_slot = ? AND group_id != ?',
                (teacher, day, time_slot, current_group_id)
            )
            return existing is None
        except Exception as e:
            print(f"⚠️ Ошибка проверки преподавателя {teacher}: {e}")
            return True

    def _smart_distribute_pairs(self, subject_distribution: Dict, max_total_slots: int = 20) -> Dict:
        """Умное распределение пар с учетом приоритетов и ограничений"""
        # Сначала распределяем минимумы для предметов с высоким приоритетом
        sorted_items = sorted(
            subject_distribution.items(),
            key=lambda x: x[1]['priority'],
            reverse=True
        )

        # Рассчитываем общее количество пар
        total_pairs_needed = sum(info['pairs_to_assign'] for _, info in sorted_items)

        # Если пар больше чем слотов, уменьшаем распределение
        if total_pairs_needed > max_total_slots:
            print(f"⚠️ Пар больше чем слотов ({total_pairs_needed} > {max_total_slots}), уменьшаем распределение")

            # Уменьшаем равномерно, сохраняя минимумы
            reduction_factor = max_total_slots / total_pairs_needed
            for key, info in subject_distribution.items():
                new_pairs = max(1, int(info['pairs_to_assign'] * reduction_factor))
                info['pairs_to_assign'] = min(new_pairs, info['pairs_to_assign'])

        return subject_distribution

    async def update_hours_after_generation(self, lessons: List[Lesson], group_id: int):
        """Обновить часы после генерации"""
        pair_counts = defaultdict(int)

        for lesson in lessons:
            key = (lesson.teacher, lesson.subject_name)
            pair_counts[key] += 1

        for (teacher, subject_name), pair_count in pair_counts.items():
            hours_to_subtract = pair_count * 2

            # Находим предмет
            subject = await database.fetch_one(
                'SELECT id, remaining_hours FROM subjects WHERE teacher = ? AND subject_name = ? AND group_id = ?',
                (teacher, subject_name, group_id)
            )

            if subject:
                subject_id, current_hours = subject
                new_hours = max(0, current_hours - hours_to_subtract)
                new_pairs = new_hours // 2

                await database.execute(
                    '''UPDATE subjects 
                       SET remaining_hours = ?,
                           remaining_pairs = ?
                       WHERE id = ?''',
                    (new_hours, new_pairs, subject_id)
                )


# Глобальный экземпляр
schedule_generator = ScheduleGenerator()