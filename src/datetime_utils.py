# src/datetime_utils.py
# Модуль для работы с датой и временем.
# TODO: При рефакторинге перенести в src/core или в src/utils.

from datetime import datetime, timezone, timedelta
from dateutil import parser

_USER_TZ = None  # Внутренняя переменная модуля (изначально пустая)

# Вызывается ОДИН раз при запуске программы для настройки часового пояса.
def init_timezone(offset_hours: int):
    global _USER_TZ
    _USER_TZ = timezone(timedelta(hours=offset_hours))

# Вспомогательная функция для проверки инициализации.
def _check_init():
    if _USER_TZ is None:
        raise RuntimeError("Модуль datetime_utils не инициализирован! Вызовите init_timezone() при старте программы.")

# Возвращает текущее время в формате БД (ISO 8601 со смещением).
def get_now_iso() -> str:
    _check_init()
    now = datetime.now(_USER_TZ)
    offset_str = now.strftime('%z')
    offset_formatted = f"{offset_str[:3]}:{offset_str[3:]}"
    return now.strftime(f'%Y-%m-%dT%H:%M:%S{offset_formatted}')

# Возвращает текущую дату в формате 'YYYY-MM-DD'.
def get_today_str() -> str:
    return get_now_iso()[:10]

# Возвращает текущую дату и время в красиво�� формате 'DD.MM.YYYY HH:MM'.
def get_now_display() -> str:
    return to_display(get_now_iso())

# Преобразует строку из БД в красивый формат для интерфейса (DD.MM.YYYY HH:MM).
def to_display(iso_str: str) -> str:
    _check_init()
    if not iso_str:
        return ""
    try:
        dt = parser.parse(iso_str)
        return dt.astimezone(_USER_TZ).strftime('%d.%m.%Y %H:%M')
    except Exception:
        return str(iso_str)

# Преобразует строку из БД в объект datetime для математических операций.
def to_datetime(iso_str: str) -> datetime:
    _check_init()
    dt = parser.parse(iso_str)
    return dt.astimezone(_USER_TZ)

# Обнуляет секунды и микросекунды в ISO 8601, сохраняя таймзону.
# Используется на границе записи в БД: MVP работает с минутной точностью.
def to_minute_iso(iso_str: str) -> str:
    """'2026-11-04T12:08:59+03:00' → '2026-11-04T12:08:00+03:00'.
    Пустая строка / None → возвращаются как есть."""
    if not iso_str:
        return iso_str
    dt = to_datetime(iso_str)
    dt = dt.replace(second=0, microsecond=0)
    return dt.isoformat()