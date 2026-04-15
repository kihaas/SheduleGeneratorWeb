from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import List
from pydantic import BaseModel

from app.services.teacher_service import teacher_service
from app.db.models import Teacher

router = APIRouter(tags=["teachers"])


class TeacherCreateRequest(BaseModel):
    name: str


class TeacherResponse(BaseModel):
    id: int
    name: str
    created_at: str


@router.post("/api/teachers", response_model=TeacherResponse)
async def create_teacher(request: TeacherCreateRequest):
    """Создать преподавателя (ГЛОБАЛЬНО - для всех групп)"""
    try:
        # Проверяем существование преподавателя
        existing = await teacher_service.get_teacher_by_name(request.name)
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Преподаватель с таким именем уже существует"
            )

        teacher = await teacher_service.create_teacher(request.name)
        return TeacherResponse(
            id=teacher.id,
            name=teacher.name,
            created_at=teacher.created_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка создания преподавателя: {str(e)}")


@router.put("/api/teachers/{teacher_id}")
async def update_teacher(teacher_id: int, request: TeacherCreateRequest):
    """Обновить преподавателя (ГЛОБАЛЬНО)"""
    try:
        teacher = await teacher_service.update_teacher(teacher_id, request.name)
        if not teacher:
            raise HTTPException(status_code=404, detail="Преподаватель не найден")

        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Преподаватель обновлен"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка обновления преподавателя: {str(e)}")


@router.get("/api/teachers/{teacher_id}", response_model=TeacherResponse)
async def get_teacher(teacher_id: int):
    """Получить преподавателя по ID"""
    try:
        teacher = await teacher_service.get_teacher(teacher_id)
        if not teacher:
            raise HTTPException(status_code=404, detail="Преподаватель не найден")

        return TeacherResponse(
            id=teacher.id,
            name=teacher.name,
            created_at=teacher.created_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения преподавателя: {str(e)}")


@router.delete("/api/teachers/{teacher_id}")
async def delete_teacher(teacher_id: int):
    """Удалить преподавателя (ГЛОБАЛЬНО - из всех групп)"""
    try:
        print(f"API: Deleting teacher {teacher_id}")
        exists = await teacher_service.teacher_exists(teacher_id)
        if not exists:
            raise HTTPException(status_code=404, detail="Преподаватель не найден")

        success = await teacher_service.delete_teacher(teacher_id)
        if not success:
            raise HTTPException(status_code=404, detail="Не удалось удалить преподавателя")

        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Преподаватель удален"}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting teacher {teacher_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка удаления преподавателя: {str(e)}")


@router.get("/api/teachers", response_model=List[TeacherResponse])
async def get_teachers():
    """Получить всех преподавателей (ГЛОБАЛЬНО - для всех групп)"""
    try:
        teachers = await teacher_service.get_all_teachers()
        return [
            TeacherResponse(
                id=teacher.id,
                name=teacher.name,
                created_at=teacher.created_at.isoformat()
            )
            for teacher in teachers
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения преподавателей: {str(e)}")


@router.get("/api/teachers/by-group/{group_id}", response_model=List[TeacherResponse])
async def get_teachers_for_group(group_id: int):
    """Получить преподавателей, которые ведут предметы в указанной группе"""
    try:
        teachers = await teacher_service.get_teachers_for_group(group_id)
        return [
            TeacherResponse(
                id=teacher.id,
                name=teacher.name,
                created_at=teacher.created_at.isoformat()
            )
            for teacher in teachers
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения преподавателей для группы: {str(e)}")


@router.get("/api/teachers/check-name")
async def check_teacher_name(name: str):
    """Проверить существует ли преподаватель с таким именем (ГЛОБАЛЬНО)"""
    try:
        existing = await teacher_service.get_teacher_by_name(name)
        return {
            "exists": existing is not None,
            "name": name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка проверки имени: {str(e)}")
