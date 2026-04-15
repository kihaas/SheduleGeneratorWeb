import sys
import os

# Добавляем родительскую папку в PYTHONPATH
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

print(f"Current directory: {current_dir}")
print(f"Parent directory: {parent_dir}")
print(f"Python path: {sys.path}")

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from app.db.database import database
import sys
from app.api.routes import api_router
from app.services.schedule_services import schedule_service
from app.services.subject_services import subject_service
from app.services.teacher_service import teacher_service  # ИСПРАВЛЕН ИМПОРТ
from app.services.group_service import group_service  # ДОБАВЛЕН ИМПОРТ
from pathlib import Path

app = FastAPI(
    title="Schedule Generator",
    description="Умный генератор учебного расписания",
    version="2.0.0",
    debug=True
)


# Mount static files and templates
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Инициализация базы данных...")
    try:
        await database.init_db()
        print("✅ База данных готова")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
    yield


app = FastAPI(
    title="Schedule Generator",
    description="Умный генератор учебного расписания",
    version="2.0.0",
    debug=True,
    lifespan=lifespan
)

# ✅ ИСПРАВЛЕННЫЕ ПУТИ - current_dir уже указывает на папку app
current_dir = Path(__file__).parent

# Пути относительно папки app
app.mount("/static", StaticFiles(directory=str(current_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(current_dir / "templates"))

app.include_router(api_router)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request, exc):
    """Обработчик HTTP исключений"""
    if exc.status_code == 500:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Внутренняя ошибка сервера"
        })
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик общих исключений"""
    print(f"❌ Необработанная ошибка: {exc}")
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error": f"Произошла ошибка: {str(exc)}"
    })


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Главная страница приложения"""
    try:
        # Получаем текущую группу из запроса (по умолчанию 1)
        group_id = int(request.query_params.get("group_id", 1))

        # Загружаем данные ДЛЯ КОНКРЕТНОЙ ГРУППЫ
        subjects = [s.model_dump() for s in await subject_service.get_all_subjects(group_id)]
        lessons = [l.model_dump() for l in await schedule_service.get_all_lessons(group_id)]

        # ПРЕПОДАВАТЕЛИ - ГЛОБАЛЬНЫЕ
        teachers = [t.model_dump() for t in await teacher_service.get_all_teachers()]

        groups = [g.model_dump() for g in await group_service.get_all_groups()]

        # Загружаем ГЛОБАЛЬНЫЕ фильтры
        try:
            from app.services.negative_filters_service import negative_filters_service
            negative_filters = await negative_filters_service.get_negative_filters()
            print(f"✅ Загружено {len(negative_filters)} ГЛОБАЛЬНЫХ фильтров")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки глобальных фильтров: {e}")
            negative_filters = {}

        # Добавьте здесь вызов статистики для логирования
        stats = await schedule_service.get_statistics(group_id)
        print(
            f"📊 Статистика главной страницы для группы {group_id}: {stats['total_subjects']} предметов, {stats['total_teachers']} преподавателей, {stats['total_hours']} часов, {stats['remaining_hours']} осталось")

        # Создаем матрицу расписания для шаблона
        schedule_matrix = [[None for _ in range(4)] for _ in range(7)]
        for lesson in lessons:
            day = lesson['day']
            time_slot = lesson['time_slot']
            if 0 <= day < 7 and 0 <= time_slot < 4:
                schedule_matrix[day][time_slot] = lesson

        # Находим текущую группу
        current_group = next((g for g in groups if g['id'] == group_id), None)
        current_group_name = current_group['name'] if current_group else "Неизвестная группа"
        print(f"🏫 Текущая группа: {current_group_name} (ID: {group_id})")

        return templates.TemplateResponse("index.html", {
            "request": request,
            "subjects": subjects,
            "teachers": teachers,
            "negative_filters": negative_filters,
            "groups": groups,  # ПЕРЕДАЕМ СПИСОК ГРУПП В ШАБЛОН
            "current_group_id": group_id,  # ПЕРЕДАЕМ ТЕКУЩУЮ ГРУППУ
            "current_group_name": current_group_name,  # ПЕРЕДАЕМ НАЗВАНИЕ ГРУППЫ
            "schedule_matrix": schedule_matrix,
            "week_days": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
            "time_slots": [
                {"start": "9:00", "end": "10:30"},
                {"start": "10:40", "end": "12:10"},
                {"start": "12:40", "end": "14:10"},
                {"start": "14:20", "end": "15:50"}
            ],
            "total_days": 7,
            "total_time_slots": 4,
            "statistics": stats  # ДОБАВЛЕНО: передаем статистику в шаблон
        })

    except Exception as e:
        print(f"❌ Ошибка загрузки главной страницы: {e}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Ошибка загрузки данных: {str(e)}"
        })


@app.get("/health")
async def health_check():
    """Проверка здоровья приложения"""
    return {
        "status": "ok",
        "message": "Service is running",
        "version": "2.0.0"
    }


if __name__ == "__main__":
    import uvicorn

    # Используем строку импорта вместо объекта app
    uvicorn.run("main:app", port=8000, reload=False)