from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import json

from app.services.schedule_services import schedule_service
from app.db.database import database
from app.db.models import Lesson

router = APIRouter(tags=["schedule-api"])


# Pydantic модели для валидации
class GenerateScheduleResponse(BaseModel):
    success: bool
    lessons: List[Dict[str, Any]]
    message: str = "Расписание успешно сгенерировано"


class LessonResponse(BaseModel):
    id: Optional[int]
    day: int
    time_slot: int
    teacher: str
    subject_name: str
    editable: bool = True
    is_past: bool = False


class RemoveLessonRequest(BaseModel):
    day: int = Field(..., ge=0, le=6, description="Day of week (0-6)")
    time_slot: int = Field(..., ge=0, le=3, description="Time slot (0-3)")


class UpdateLessonRequest(BaseModel):
    day: int = Field(..., ge=0, le=6, description="Day of week (0-6)")
    time_slot: int = Field(..., ge=0, le=3, description="Time slot (0-3)")
    new_teacher: str = Field(..., min_length=1, max_length=100, description="New teacher name")
    new_subject_name: str = Field(..., min_length=1, max_length=100, description="New subject name")


class SaveScheduleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Schedule name")
    lessons: List[Dict[str, Any]] = Field(..., description="List of lessons")


class SavedScheduleResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    lesson_count: int


# app/api/routes/schedule_api.py
# app/api/routes/schedule_api.py
@router.post("/api/schedule/generate", response_model=GenerateScheduleResponse)
async def generate_schedule(group_id: int = Query(1, description="ID группы")):
    """Сгенерировать расписание с учетом ВСЕХ параметров"""
    try:
        from app.services.shedule_generator import schedule_generator

        print(f"⚡ Генерация расписания для группы {group_id}")

        # Генерируем расписание
        lessons = await schedule_generator.generate_schedule(group_id)

        # Конвертируем в словари для JSON
        lessons_data = []
        for lesson in lessons:
            lesson_dict = {
                "day": lesson.day,
                "time_slot": lesson.time_slot,
                "teacher": lesson.teacher,
                "subject_name": lesson.subject_name,
                "editable": lesson.editable
            }
            if hasattr(lesson, 'id') and lesson.id:
                lesson_dict["id"] = lesson.id
            lessons_data.append(lesson_dict)

        return GenerateScheduleResponse(
            success=True,
            lessons=lessons_data,
            message=f"Сгенерировано {len(lessons)} пар для группы {group_id}"
        )

    except Exception as e:
        print(f"❌ Ошибка генерации расписания: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка генерации расписания: {str(e)}"
        )


@router.get("/api/schedules", response_model=List[SavedScheduleResponse])
async def get_saved_schedules(group_id: int = Query(1, description="ID группы")):
    """Получить список сохраненных расписаний группы"""
    try:
        rows = await database.fetch_all('''
            SELECT id, name, created_at, payload 
            FROM saved_schedules 
            WHERE group_id = ?
            ORDER BY created_at DESC
        ''', (group_id,))

        schedules = []
        for row in rows:
            id, name, created_at, payload = row
            lesson_count = 0

            try:
                payload_data = json.loads(payload)
                lesson_count = len(payload_data.get("lessons", []))
            except:
                pass

            schedules.append(SavedScheduleResponse(
                id=id,
                name=name,
                created_at=created_at,
                lesson_count=lesson_count
            ))

        return schedules

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения расписаний: {str(e)}"
        )


@router.post("/api/schedules/save")
async def save_schedule(request: SaveScheduleRequest, group_id: int = Query(1, description="ID группы")):
    """Сохранить расписание для группы"""
    try:
        payload = json.dumps({
            "lessons": request.lessons,
            "saved_at": datetime.now().isoformat(),
            "group_id": group_id
        })

        result = await database.execute(
            'INSERT INTO saved_schedules (name, payload, group_id) VALUES (?, ?, ?)',
            (request.name, payload, group_id)
        )

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Расписание сохранено",
                "schedule_id": result.lastrowid
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка сохранения расписания: {str(e)}"
        )


@router.get("/api/schedules/{schedule_id}")
async def get_schedule_detail(schedule_id: int):
    """Получить детали сохраненного расписания"""
    try:
        row = await database.fetch_one(
            'SELECT id, name, created_at, payload FROM saved_schedules WHERE id = ?',
            (schedule_id,)
        )

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Расписание не найдено"
            )

        id, name, created_at, payload = row

        try:
            payload_data = json.loads(payload)
        except json.JSONDecodeError:
            payload_data = {"lessons": [], "error": "Invalid JSON"}

        return JSONResponse(
            status_code=200,
            content={
                "id": id,
                "name": name,
                "created_at": created_at,
                "lessons": payload_data.get("lessons", []),
                "saved_at": payload_data.get("saved_at")
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения расписания: {str(e)}"
        )


@router.delete("/api/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int):
    """Удалить сохраненное расписание"""
    try:
        result = await database.execute(
            'DELETE FROM saved_schedules WHERE id = ?',
            (schedule_id,)
        )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Расписание не найдено"
            )

        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Расписание удалено"}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка удаления расписания: {str(e)}"
        )


@router.get("/api/schedule/check-teacher")
async def check_teacher_availability(
        teacher: str = Query(..., description="Имя преподавателя"),
        day: int = Query(..., ge=0, le=6, description="День недели"),
        time_slot: int = Query(..., ge=0, le=3, description="Временной слот"),
        group_id: int = Query(1, description="ID группы")
):
    """Проверить доступность преподавателя в указанный слот"""
    try:
        from app.services.shedule_generator import schedule_generator

        available = await schedule_generator.can_assign_teacher(teacher, day, time_slot, group_id)

        return {
            "teacher": teacher,
            "day": day,
            "time_slot": time_slot,
            "group_id": group_id,
            "available": available,
            "message": "Доступен" if available else "Занят в другой группе или имеет ограничения"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка проверки доступности: {str(e)}"
        )

