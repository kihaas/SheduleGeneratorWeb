import sys
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

# ====================== ИМПОРТЫ АВТОРИЗАЦИИ ======================
from app.api.routes.auth import get_optional_user

# ====================== ТВОИ СЕРВИСЫ ======================
from app.db.database import database
from app.api.routes import api_router
from app.services.schedule_services import schedule_service
from app.services.subject_services import subject_service
from app.services.teacher_service import teacher_service
from app.services.group_service import group_service

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


# ====================== LIFESPAN ======================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Инициализация базы данных...")
    try:
        await database.init_db()
        print("✅ База данных готова")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
    yield


# ====================== СОЗДАНИЕ ПРИЛОЖЕНИЯ ======================
app = FastAPI(
    title="Schedule Generator",
    description="Умный генератор учебного расписания",
    version="2.0.0",
    debug=True,
    lifespan=lifespan,
    redirect_slashes=False
)

# ====================== STATIC + TEMPLATES ======================
current_dir = Path(__file__).parent

app.mount("/static", StaticFiles(directory=str(current_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(current_dir / "templates"))

# ====================== ПОДКЛЮЧЕНИЕ РОУТЕРОВ ======================
app.include_router(api_router)


# ====================== СТРАНИЦЫ АВТОРИЗАЦИИ ======================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Если уже вошли — редирект на главную
    user = await get_optional_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    # Если уже вошли — редирект на главную
    user = await get_optional_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request})


# ====================== ГЛАВНАЯ СТРАНИЦА (ГОСТЕВОЙ РЕЖИМ) ======================
@app.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request,
    current_user: dict = Depends(get_optional_user)   # ← мягкая проверка, не кидает 401
):
    """
    Главная страница доступна всем.
    - Гость (current_user=None): данные только в sessionStorage, в шапке кнопки Войти/Регистрация
    - Авторизованный: данные из БД, в шапке иконка + Выйти
    """
    try:
        group_id = int(request.query_params.get("group_id", 1))

        subjects = [s.model_dump() for s in await subject_service.get_all_subjects(group_id)]
        lessons = [l.model_dump() for l in await schedule_service.get_all_lessons(group_id)]
        teachers = [t.model_dump() for t in await teacher_service.get_all_teachers()]
        groups = [g.model_dump() for g in await group_service.get_all_groups()]

        try:
            from app.services.negative_filters_service import negative_filters_service
            negative_filters = await negative_filters_service.get_negative_filters()
        except Exception as e:
            print(f"⚠️ Ошибка загрузки фильтров: {e}")
            negative_filters = {}

        stats = await schedule_service.get_statistics(group_id)

        schedule_matrix = [[None for _ in range(4)] for _ in range(7)]
        for lesson in lessons:
            day = lesson.get('day')
            time_slot = lesson.get('time_slot')
            if 0 <= day < 7 and 0 <= time_slot < 4:
                schedule_matrix[day][time_slot] = lesson

        current_group = next((g for g in groups if g.get('id') == group_id), None)
        current_group_name = current_group.get('name') if current_group else "Неизвестная группа"

        return templates.TemplateResponse("index.html", {
            "request": request,
            "subjects": subjects,
            "teachers": teachers,
            "negative_filters": negative_filters,
            "groups": groups,
            "current_group_id": group_id,
            "current_group_name": current_group_name,
            "schedule_matrix": schedule_matrix,
            "week_days": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
            "time_slots": [
                {"start": "9:00", "end": "10:30"},
                {"start": "10:40", "end": "12:10"},
                {"start": "12:40", "end": "14:10"},
                {"start": "14:20", "end": "15:50"}
            ],
            "statistics": stats,
            "user": current_user   # None если гость, dict если авторизован
        })

    except Exception as e:
        print(f"❌ Ошибка загрузки главной страницы: {e}")
        import traceback
        print(traceback.format_exc())
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Ошибка загрузки данных: {str(e)}"
        })


# ====================== ОБРАБОТЧИКИ ОШИБОК ======================
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    # 401 только для API-эндпоинтов, не для страниц
    if exc.status_code == 401 and request.url.path.startswith("/auth"):
        return await http_exception_handler(request, exc)
    if exc.status_code == 500:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Внутренняя ошибка сервера"
        }, status_code=500)
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    print(f"❌ Необработанная ошибка: {exc}")
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error": f"Произошла ошибка: {str(exc)}"
    }, status_code=500)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)