from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

from app.db import database
from app.services.manual_schedule_service import manual_schedule_service
from app.services.subject_services import subject_service

router = APIRouter(tags=["manual-schedule"])


class AddLessonRequest(BaseModel):
    """Запрос на добавление пары вручную"""
    day: int = Field(..., ge=0, le=6, description="День недели (0-6)")
    time_slot: int = Field(..., ge=0, le=3, description="Временной слот (0-3)")
    teacher: str = Field(..., min_length=1, max_length=100, description="Преподаватель")
    subject_name: str = Field(..., min_length=1, max_length=100, description="Название предмета")


class UpdateLessonRequest(BaseModel):
    """Запрос на обновление пары (совместимый с существующим)"""
    day: int = Field(..., ge=0, le=6, description="День недели (0-6)")
    time_slot: int = Field(..., ge=0, le=3, description="Временной слот (0-3)")
    new_teacher: str = Field(..., min_length=1, max_length=100, description="Новый преподаватель")
    new_subject_name: str = Field(..., min_length=1, max_length=100, description="Новое название предмета")


@router.post("/api/manual/lessons")
async def add_lesson_manually(
        request: AddLessonRequest,
        group_id: int = Query(1, description="ID группы")
):
    """Добавить пару вручную в указанный слот"""
    try:
        result = await manual_schedule_service.add_lesson(
            day=request.day,
            time_slot=request.time_slot,
            teacher=request.teacher,
            subject_name=request.subject_name,
            group_id=group_id
        )

        if result["success"]:
            return JSONResponse(
                status_code=201,
                content=result
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка добавления пары: {str(e)}"
        )


# В файл manual.py добавляем:

@router.delete("/api/manual/lessons")
async def delete_lesson_manually(
        day: int = Query(..., ge=0, le=6, description="День недели (0-6)"),
        time_slot: int = Query(..., ge=0, le=3, description="Временной слот (0-3)"),
        group_id: int = Query(1, description="ID группы")
):
    """Удалить пару вручную"""
    try:
        print(f"🗑️ Ручное удаление пары: день={day}, слот={time_slot}, группа={group_id}")

        # 1. Получаем удаляемый урок
        lesson = await database.fetch_one(
            'SELECT teacher, subject_name FROM lessons WHERE day = ? AND time_slot = ? AND group_id = ?',
            (day, time_slot, group_id)
        )

        if not lesson:
            raise HTTPException(
                status_code=404,
                detail="Урок не найден"
            )

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

        # 3. Удаляем урок
        result = await database.execute(
            'DELETE FROM lessons WHERE day = ? AND time_slot = ? AND group_id = ?',
            (day, time_slot, group_id)
        )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=500,
                detail="Не удалось удалить урок"
            )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Пара успешно удалена"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка удаления пары: {str(e)}"
        )


@router.patch("/api/manual/lessons")
async def update_lesson_manually(
        request: UpdateLessonRequest,
        group_id: int = Query(1, description="ID группы")
):
    """Обновить или добавить пару (универсальный метод)"""
    try:
        print("=" * 50)
        print("🔄 PATCH /api/manual/lessons - ОБНОВЛЕНИЕ ПАРЫ")
        print(f"📥 Данные запроса: day={request.day}, time_slot={request.time_slot}")
        print(f"📥 Преподаватель: '{request.new_teacher}'")
        print(f"📥 Предмет: '{request.new_subject_name}'")
        print(f"📥 Группа: {group_id}")

        result = await manual_schedule_service.update_lesson(
            day=request.day,
            time_slot=request.time_slot,
            new_teacher=request.new_teacher,
            new_subject_name=request.new_subject_name,
            group_id=group_id
        )

        print(f"📤 Результат: success={result['success']}, message={result['message']}")

        if result["success"]:
            return JSONResponse(
                status_code=200,
                content=result
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result["message"]
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Неожиданная ошибка: {e}")
        import traceback
        print(f"💥 Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера: {str(e)}"
        )
    finally:
        print("=" * 50)

@router.get("/api/manual/check-availability")
async def check_availability(
        teacher: str = Query(..., description="Преподаватель"),
        day: int = Query(..., ge=0, le=6, description="День недели"),
        time_slot: int = Query(..., ge=0, le=3, description="Временной слот"),
        group_id: int = Query(1, description="ID группы")
):
    """Проверить доступность преподавателя в указанном слоте"""
    try:
        available, message = await manual_schedule_service.check_teacher_availability(
            teacher=teacher,
            day=day,
            time_slot=time_slot,
            current_group_id=group_id
        )

        return {
            "teacher": teacher,
            "day": day,
            "time_slot": time_slot,
            "available": available,
            "message": message,
            "group_id": group_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка проверки доступности: {str(e)}"
        )


@router.get("/api/manual/available-subjects")
async def get_available_subjects(
        group_id: int = Query(1, description="ID группы")
):
    """Получить список предметов, которые можно добавить (с оставшимися парами)"""
    try:
        from app.services.subject_services import subject_service

        subjects = await subject_service.get_all_subjects(group_id)

        available_subjects = []
        for subject in subjects:
            if subject.remaining_pairs > 0:
                available_subjects.append({
                    "id": subject.id,
                    "teacher": subject.teacher,
                    "subject_name": subject.subject_name,
                    "remaining_pairs": subject.remaining_pairs,
                    "total_hours": subject.total_hours,
                    "remaining_hours": subject.remaining_hours,
                    "max_per_day": subject.max_per_day
                })

        return {
            "group_id": group_id,
            "available_subjects": available_subjects,
            "count": len(available_subjects)
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения доступных предметов: {str(e)}"
        )