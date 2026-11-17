# src/web_sync.py
# Синхронизация с веб-API slqa.ru/z/api.
# Тупо переносит события в web_time_events, удаляет на сервере.
# Дедупликация — только в web_events_service.py (при создании сна).

import logging
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

from . import datetime_utils
from .web_time_events_repo import WebTimeEventsRepository

logger = logging.getLogger(__name__)


def _api_call(method: str, url: str, api_key: str, **kwargs):
    if requests is None:
        raise RuntimeError(
            "Библиотека 'requests' не установлена. Выполните: pip install requests"
        )
    headers = kwargs.pop("headers", {})
    headers["X-API-Key"] = api_key
    return requests.request(method, url, headers=headers, timeout=15, **kwargs)


def fetch_events(api_url: str, api_key: str) -> list[dict]:
    resp = _api_call("GET", f"{api_url.rstrip('/')}/events/", api_key)
    resp.raise_for_status()
    return resp.json()


def delete_event(api_url: str, api_key: str, event_id: int) -> None:
    resp = _api_call("DELETE", f"{api_url.rstrip('/')}/events/{event_id}", api_key)
    # 204 — успех, 404 — уже удалено (идемпотентность)
    if resp.status_code not in (204, 404):
        resp.raise_for_status()


def _to_local_iso(utc_str: str) -> str:
    """'YYYY-MM-DD HH:MM:SS' (UTC) → ISO 8601 с UTC+3."""
    dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    local = dt.astimezone(datetime_utils._USER_TZ)
    return local.isoformat()  # '2026-11-03T03:31:43+03:00'


def sync(prefs_repo) -> dict:
    """Основная функция синхронизации.

    Возвращает dict:
        {"ok": bool, "fetched": int, "inserted": int,
         "skipped": int, "deleted": int, "errors": [str]}
    """
    result = {
        "ok": False,
        "fetched": 0,
        "inserted": 0,
        "skipped": 0,
        "deleted": 0,
        "errors": [],
    }

    api_url = prefs_repo.get("web_sync_url") or ""
    api_key = prefs_repo.get("web_sync_key") or ""

    if not api_url or not api_key:
        result["errors"].append("web_sync_url или web_sync_key не заданы")
        return result

    # 1. Получить события
    try:
        events = fetch_events(api_url, api_key)
    except Exception as e:
        logger.exception("web_sync fetch failed")
        result["errors"].append(f"fetch: {e}")
        return result

    result["fetched"] = len(events)
    if not events:
        result["ok"] = True
        return result

    db = prefs_repo.db
    repo = WebTimeEventsRepository(db)
    now_iso = datetime_utils.get_now_iso()

    # 2. INSERT OR IGNORE
    for ev in events:
        try:
            local_iso = _to_local_iso(ev["event_time"])
            new_id = repo.add(
                server_event_id=ev["id"],
                event_type=ev["event_type"],
                event_time=local_iso,
                created_at=now_iso,
            )
            if new_id is not None:
                result["inserted"] += 1
            else:
                result["skipped"] += 1
        except Exception as e:
            logger.exception("web_sync save failed for id=%s", ev.get("id"))
            result["errors"].append(f"save id={ev.get('id')}: {e}")

    # 3. DELETE на сервере для ВСЕХ событий (и новых, и уже бывших)
    for ev in events:
        try:
            delete_event(api_url, api_key, ev["id"])
            result["deleted"] += 1
        except Exception as e:
            logger.exception("web_sync delete failed for id=%s", ev.get("id"))
            result["errors"].append(f"delete id={ev.get('id')}: {e}")

    result["ok"] = len(result["errors"]) == 0
    return result