from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.services.exel_exporter import excel_exporter
import json
import urllib.parse

router = APIRouter(tags=["export"])


@router.get("/api/export/schedule/{schedule_id}")
async def export_schedule_excel(schedule_id: int):
    """Экспорт сохраненного расписания в Excel"""
    try:
        # Получаем имя расписания из БД
        from app.db.database import database
        row = await database.fetch_one(
            'SELECT name, payload FROM saved_schedules WHERE id = ?',
            (schedule_id,)
        )

        if not row:
            raise HTTPException(status_code=404, detail="Расписание не найдено")

        name, payload = row
        schedule_name = name

        # Парсим payload и получаем уроки
        payload_data = json.loads(payload)
        lessons = payload_data.get('lessons', [])

        # Генерируем Excel
        excel_data = await excel_exporter.export_schedule_to_excel(lessons, schedule_name)

        # Формируем имя файла (безопасное для кодировки)
        safe_filename = schedule_name.replace(' ', '_')
        safe_filename = ''.join(c for c in safe_filename if c.isalnum() or c in ('_', '-'))
        if not safe_filename:
            safe_filename = "schedule"
        filename = f"{safe_filename}.xlsx"

        # Кодируем имя файла для заголовка Content-Disposition
        encoded_filename = urllib.parse.quote(filename)

        return Response(
            content=excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        print(f"❌ Ошибка экспорта: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка экспорта: {str(e)}")