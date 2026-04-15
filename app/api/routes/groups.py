from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import List
from pydantic import BaseModel

from app.services.group_service import group_service
from app.db.models import StudyGroup, StudyGroupCreate

router = APIRouter(tags=["groups"])


class GroupCreateRequest(BaseModel):
    name: str


class GroupUpdateRequest(BaseModel):
    name: str


@router.get("/api/groups", response_model=List[StudyGroup])
async def get_all_groups():
    """Получить все группы"""
    try:
        groups = await group_service.get_all_groups()
        return groups
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения групп: {str(e)}")


@router.post("/api/groups", response_model=StudyGroup)
async def create_group(request: GroupCreateRequest):
    """Создать новую группу"""
    try:
        if not request.name or not request.name.strip():
            raise HTTPException(status_code=400, detail="Название группы не может быть пустым")

        group = await group_service.create_group(request.name.strip())
        return group

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка создания группы: {str(e)}")


@router.put("/api/groups/{group_id}", response_model=StudyGroup)
async def update_group(group_id: int, request: GroupUpdateRequest):
    """Переименовать группу"""
    try:
        if not request.name or not request.name.strip():
            raise HTTPException(status_code=400, detail="Название группы не может быть пустым")

        group = await group_service.update_group(group_id, request.name.strip())
        return group

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления группы: {str(e)}")


@router.delete("/api/groups/{group_id}")
async def delete_group(group_id: int):
    """Удалить группу"""
    try:
        success = await group_service.delete_group(group_id)

        if not success:
            raise HTTPException(status_code=404, detail="Группа не найдена")

        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Группа и все её данные удалены"}
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления группы: {str(e)}")


@router.get("/api/groups/{group_id}/exists")
async def check_group_exists(group_id: int):
    """Проверить существование группы"""
    try:
        exists = await group_service.group_exists(group_id)
        return {"exists": exists}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка проверки группы: {str(e)}")