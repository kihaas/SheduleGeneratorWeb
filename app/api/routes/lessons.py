from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import traceback

from app.services.schedule_services import schedule_service
from app.db.models import Lesson

router = APIRouter(tags=["lessons"])


# class UpdateLessonRequest(BaseModel):
#     day: int
#     time_slot: int
#     new_teacher: str
#     new_subject_name: str


class LessonResponse(BaseModel):
    id: Optional[int]
    day: int
    time_slot: int
    teacher: str
    subject_name: str
    editable: bool = True
    is_past: bool = False


@router.get("/api/lessons", response_model=List[LessonResponse])
async def get_all_lessons(group_id: int = Query(1, description="ID группы")):
    """Получить все уроки группы"""
    try:
        lessons = await schedule_service.get_all_lessons(group_id)
        return lessons
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения уроков: {str(e)}"
        )


# @router.post("/remove-lesson")
# async def remove_lesson_old(day: int = Form(...), time_slot: int = Form(...)):
#     """Старый эндпоинт для обратной совместимости (HTML формы)"""
#     try:
#         success = await schedule_service.remove_lesson(day, time_slot)
#         if not success:
#             raise HTTPException(status_code=404, detail="Lesson not found")
#         return RedirectResponse(url="/", status_code=303)
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))


@router.post("/remove-lesson")
async def remove_lesson(day: int = Form(...), time_slot: int = Form(...)):
    try:
        success = await schedule_service.remove_lesson(day, time_slot)
        if not success:
            raise HTTPException(status_code=404, detail="Lesson not found")
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/lessons")
async def remove_lesson_api(
        day: int = Query(..., ge=0, le=6, description="Day of week (0-6)"),
        time_slot: int = Query(..., ge=0, le=3, description="Time slot (0-3)"),
        group_id: int = Query(1, description="ID группы")
):
    """Удалить урок по дню и временному слоту (JSON API)"""
    try:
        print(f"🗑️ Удаление урока: день {day}, слот {time_slot}, группа {group_id}")

        success = await schedule_service.remove_lesson(day, time_slot, group_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Урок не найден или не может быть удален"
            )

        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Урок успешно удален"}
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка удаления урока: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка удаления урока: {str(e)}"
        )


@router.post("/update-lesson")
async def update_lesson_old(
        day: int = Form(...),
        time_slot: int = Form(...),
        teacher: str = Form(...),
        subject_name: str = Form(...)
):
    """Старый эндпоинт для обратной совместимости (HTML формы)"""
    try:
        print(f"📨 Старый формат обновления: день {day}, слот {time_slot}")

        # Базовая валидация для старого формата
        if not teacher or not subject_name:
            raise HTTPException(status_code=400, detail="Заполните все поля")

        cleaned_teacher = teacher.strip()
        cleaned_subject = subject_name.strip()

        if len(cleaned_teacher) < 1 or len(cleaned_subject) < 1:
            raise HTTPException(status_code=400, detail="Поля не могут быть пустыми")

        success = await schedule_service.update_lesson(day, time_slot, cleaned_teacher, cleaned_subject)

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Не удалось обновить урок - возможно, урок не редактируемый или не найден"
            )

        return RedirectResponse(url="/", status_code=303)

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка в старом эндпоинте: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Дополнительные эндпоинты для удобства
@router.get("/api/lessons/{day}/{time_slot}")
async def get_lesson_detail(
        day: int,
        time_slot: int,
        group_id: int = Query(1, description="ID группы")
):
    """Получить информацию об уроке в конкретном слоте"""
    try:
        # Ищем урок в общем списке
        lessons = await schedule_service.get_all_lessons(group_id)
        lesson = next(
            (l for l in lessons if l.day == day and l.time_slot == time_slot),
            None
        )

        if not lesson:
            raise HTTPException(
                status_code=404,
                detail="Урок не найден"
            )

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "lesson": {
                    "day": lesson.day,
                    "time_slot": lesson.time_slot,
                    "teacher": lesson.teacher,
                    "subject_name": lesson.subject_name,
                    "editable": getattr(lesson, 'editable', True),
                    "group_id": group_id
                }
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ошибка получения урока: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения урока: {str(e)}"
        )


@router.get("/api/lessons/check-slot")
async def check_slot_availability(
        day: int = Query(..., ge=0, le=6),
        time_slot: int = Query(..., ge=0, le=3),
        group_id: int = Query(1, description="ID группы")
):
    """Проверить доступность слота"""
    try:
        lessons = await schedule_service.get_all_lessons(group_id)
        is_occupied = any(
            l.day == day and l.time_slot == time_slot
            for l in lessons
        )

        return JSONResponse(
            status_code=200,
            content={
                "day": day,
                "time_slot": time_slot,
                "is_occupied": is_occupied,
                "available": not is_occupied,
                "group_id": group_id
            }
        )

    except Exception as e:
        print(f"❌ Ошибка проверки слота: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка проверки доступности слота: {str(e)}"
        )