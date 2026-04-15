from fastapi import APIRouter, HTTPException, Form, Query
from fastapi.responses import JSONResponse, RedirectResponse
from typing import List
from pydantic import BaseModel

from app.services.negative_filters_service import negative_filters_service

router = APIRouter(tags=["negative-filters"])


class NegativeFilterRequest(BaseModel):
    teacher: str
    restricted_days: List[int] = []
    restricted_slots: List[int] = []


@router.post("/api/negative-filters")
async def add_negative_filter_api(request: NegativeFilterRequest):
    """Добавить ГЛОБАЛЬНЫЕ ограничения для преподавателя через JSON"""
    try:
        print(f"🌍 Сохранение ГЛОБАЛЬНЫХ ограничений: teacher={request.teacher}")

        await negative_filters_service.save_negative_filter(
            request.teacher,
            request.restricted_days,
            request.restricted_slots
        )

        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Глобальные ограничения сохранены"}
        )
    except Exception as e:
        print(f"❌ Ошибка сохранения глобальных ограничений: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка сохранения ограничений: {str(e)}")


@router.get("/api/negative-filters")
async def get_negative_filters_api():
    """Получить ВСЕ глобальные ограничения"""
    try:
        filters = await negative_filters_service.get_negative_filters()
        print(f"✅ API: Отправлено {len(filters)} глобальных фильтров")
        return filters
    except Exception as e:
        print(f"❌ API Ошибка получения ограничений: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения ограничений: {str(e)}")

# Для обратной совместимости с фронтендом, который может передавать group_id
@router.get("/api/negative-filters/by-group/{group_id}")
async def get_negative_filters_by_group_api(group_id: int):
    """Устаревший эндпоинт - теперь возвращает глобальные фильтры"""
    try:
        filters = await negative_filters_service.get_negative_filters()
        print(f"✅ API (group_id={group_id}): Отправлено {len(filters)} глобальных фильтров")
        return filters
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения ограничений: {str(e)}")

@router.delete("/api/negative-filters/{teacher}")
async def remove_negative_filter_api(teacher: str):
    """Удалить ГЛОБАЛЬНЫЕ ограничения для преподавателя"""
    try:
        await negative_filters_service.remove_negative_filter(teacher)
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Глобальные ограничения удалены"}
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка удаления ограничений: {str(e)}")


