from fastapi import APIRouter
from . import schedule, subjects, lessons, teachers, negative_filters, statistics, schedule_api, export, groups, manual, auth

api_router = APIRouter()

api_router.include_router(schedule.router)
api_router.include_router(subjects.router)
api_router.include_router(lessons.router)
api_router.include_router(teachers.router)
api_router.include_router(statistics.router)
api_router.include_router(negative_filters.router)

api_router.include_router(schedule_api.router)
api_router.include_router(export.router)

api_router.include_router(groups.router)

api_router.include_router(manual.router)
api_router.include_router(auth.router)