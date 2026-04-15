from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db import database
from app.services.schedule_services import schedule_service

router = APIRouter(tags=["statistics"])


class StatisticsResponse(BaseModel):
    total_subjects: int
    total_teachers: int
    total_hours: int
    remaining_hours: int
    scheduled_pairs: int
    remaining_pairs: int


@router.get("/api/statistics", response_model=StatisticsResponse)
async def get_statistics(group_id: int = Query(1, description="ID группы")):  # ДОБАВЬТЕ ПАРАМЕТР
    """Получить статистику"""
    try:
        stats = await schedule_service.get_statistics(group_id)  # ПЕРЕДАЙТЕ group_id
        return StatisticsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")


@router.post("/api/statistics/recalculate")
async def recalculate_statistics(group_id: int = Query(1, description="ID группы")):
    """Пересчитать статистику часов для группы"""
    try:
        # Пересчитываем оставшиеся часы на основе запланированных пар
        lessons = await database.fetch_all(
            'SELECT teacher, subject_name, COUNT(*) as count FROM lessons WHERE group_id = ? GROUP BY teacher, subject_name',
            (group_id,)
        )

        # Сбрасываем все часы к исходным значениям
        await database.execute(
            '''UPDATE subjects 
               SET remaining_hours = total_hours,
                   remaining_pairs = total_hours / 2 
               WHERE group_id = ?''',
            (group_id,)
        )

        # Вычитаем часы для запланированных пар
        for lesson in lessons:
            teacher, subject_name, count = lesson
            hours_to_subtract = count * 2

            result = await database.execute(
                '''UPDATE subjects 
                   SET remaining_hours = remaining_hours - ?, 
                       remaining_pairs = remaining_pairs - ? 
                   WHERE teacher = ? AND subject_name = ? AND group_id = ?''',
                (hours_to_subtract, count, teacher, subject_name, group_id)
            )

            if result.rowcount == 0:
                print(f"⚠️ Предмет не найден: {teacher} - {subject_name} в группе {group_id}")

        # Получаем обновленную статистику
        stats = await schedule_service.get_statistics(group_id)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Статистика для группы {group_id} пересчитана",
                "statistics": stats
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка пересчета статистики: {str(e)}")


@router.post("/api/statistics/fix-hours")
async def fix_hours_calculation(group_id: int = Query(1, description="ID группы")):
    """Исправить расчет часов (принудительный пересчет)"""
    try:
        print(f"🔧 Исправление расчета часов для группы {group_id}")

        # 1. Сбрасываем все часы к исходным значениям
        await database.execute(
            '''UPDATE subjects 
               SET remaining_hours = total_hours,
                   remaining_pairs = total_hours / 2 
               WHERE group_id = ?''',
            (group_id,)
        )

        # 2. Считаем сколько пар запланировано для каждого предмета
        lessons = await database.fetch_all(
            '''SELECT teacher, subject_name, COUNT(*) as pair_count 
               FROM lessons 
               WHERE group_id = ? 
               GROUP BY teacher, subject_name''',
            (group_id,)
        )

        print(f"📊 Найдено запланированных пар: {len(lessons)}")

        # 3. Вычитаем часы для запланированных пар
        for lesson in lessons:
            teacher, subject_name, pair_count = lesson
            hours_to_subtract = pair_count * 2  # 2 часа на пару

            # Находим предмет
            subject = await database.fetch_one(
                '''SELECT id, remaining_hours, total_hours 
                   FROM subjects 
                   WHERE teacher = ? AND subject_name = ? AND group_id = ?''',
                (teacher, subject_name, group_id)
            )

            if subject:
                subject_id, current_hours, total_hours = subject
                new_hours = max(0, current_hours - hours_to_subtract)
                new_pairs = new_hours // 2

                await database.execute(
                    '''UPDATE subjects 
                       SET remaining_hours = ?,
                           remaining_pairs = ?
                       WHERE id = ?''',
                    (new_hours, new_pairs, subject_id)
                )

                print(f"📝 {teacher} - {subject_name}: было {current_hours}ч, стало {new_hours}ч ({pair_count} пар)")

        # 4. Получаем обновленную статистику
        stats = await schedule_service.get_statistics(group_id)

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Расчет часов исправлен для группы {group_id}",
                "statistics": stats
            }
        )
    except Exception as e:
        print(f"❌ Ошибка исправления часов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка исправления часов: {str(e)}")


