# src/web_events_service.py
# Создание активности «Ночной сон» из web-событий.
#
# Алгоритм:
#   1. Окно [D-1 H:00, D H:00), где H = web_events_sleep_window_start_hour.
#   2. Взять необработанные события в окне.
#   3. Проверить, что события каждого типа (sleep / wake) укладываются
#      в окно дедупликации (web_events_dedupe_window_sec) от первого события
#      своего типа. Если нет — ошибка с перечислением всех событий типа.
#   4. Дедупликация:
#        sleep — оставляем ПОСЛЕДНЕЕ в кластере (реальный отбой);
#        wake  — оставляем ПЕРВОЕ в кластере (реальный подъём).
#   5. start = последний sleep; end = первый wake после него.
#   6. Проверки: end > start, за D ещё нет ночного сна.
#   7. Создать активность id=1 «Ночной сон».
#   8. Пометить все события в окне как processed=1.
#
# Во всех ошибках, где есть события, выводится полный список событий
# (тип + время), чтобы пользователь сразу видел, на каких данных возникла
# проблема (например, нажал не ту кнопку и получил неверную дату окна).
#
# Если настройки (web_events_sleep_window_start_hour, web_events_dedupe_window_sec)
# отсутствуют в preferences — падаем с явной ошибкой (не подставляем дефолт молча).

import logging
from datetime import datetime, timedelta

from . import datetime_utils
from .web_time_events_repo import WebTimeEventsRepository
from .activities_repo import ActivitiesRepository
from .activity_types_repo import ActivityTypesRepository

logger = logging.getLogger(__name__)

SLEEP_TYPE_ID = 1  # «Ночной сон» — жёстко зашит в миграции 005


def _require_int_pref(prefs_repo, key: str) -> int:
    """Возвращает значение preference как int. Если ключ отсутствует (None) —
    бросает ValueError. Если значение не парсится в int — тоже ValueError."""
    val = prefs_repo.get(key)
    if val is None:
        raise ValueError(
            f"Настройка '{key}' отсутствует в preferences. "
            f"Проверьте src/defaults.py и перезапустите приложение."
        )
    try:
        return int(val)
    except (TypeError, ValueError):
        raise ValueError(
            f"Настройка '{key}' имеет некорректное значение: {val!r} (ожидалось целое число)."
        )


def _parse_iso(s: str) -> datetime:
    """Парсит ISO 8601 (с TZ) → aware datetime в UTC+3."""
    return datetime_utils.to_datetime(s)


def _format_events_list(events: list[dict], label: str = "Список текущих записей:") -> str:
    """Форматирует список событий для сообщения об ошибке.

    Каждое событие — отдельной строкой: "  - {event_type}: {event_time}".
    Если список пуст — возвращает пустую строку.
    """
    if not events:
        return ""
    lines = [label]
    for ev in events:
        lines.append(f"  - {ev['event_type']}: {ev['event_time']}")
    return "\n".join(lines)


def _check_events_fit_window(events: list[dict], event_type: str, window_sec: int) -> str | None:
    """Проверяет, что все события указанного типа укладываются в окно window_sec
    от первого события этого типа.

    Returns:
        None, если событий типа < 2 или разброс <= window_sec.
        str — текст ошибки с перечислением ВСЕХ событий типа, если разброс > window_sec.
    """
    typed = [e for e in events if e["event_type"] == event_type]
    if len(typed) < 2:
        return None

    times = sorted(_parse_iso(e["event_time"]) for e in typed)
    spread = (times[-1] - times[0]).total_seconds()
    if spread <= window_sec:
        return None

    msg = (
        f"События «{event_type}» не укладываются в окно дедупликации "
        f"({window_sec}с / {window_sec / 3600:.1f}ч). "
        f"Всего событий: {len(typed)}, разброс: {int(spread)}с / "
        f"{int(spread // 3600)}ч{int((spread % 3600) // 60)}м."
    )
    msg += "\n" + _format_events_list(typed, "Список текущих записей:")
    msg += "\nУвеличьте web_events_dedupe_window_sec или проверьте события на сервере."
    return msg


def _dedupe(events: list[dict], window_sec: int) -> list[dict]:
    """Схлопывает дубли одного типа в пределах window_sec секунд.

    events: [{"id", "server_event_id", "event_type", "event_time"}, ...]
    Возвращает список оставленных событий, отсортированный по event_time.

    Логика внутри кластера:
      - sleep: оставляем ПОСЛЕДНЕЕ событие кластера (реальный отбой,
        а не первое нажатие);
      - wake: оставляем ПЕРВОЕ событие кластера (реальный подъём,
        а не последнее нажатие).

    Окно кластера определяется от первого события (last_time не сдвигается
    при замене sleep-события).
    """
    by_type: dict[str, list[dict]] = {}
    for ev in events:
        by_type.setdefault(ev["event_type"], []).append(ev)

    kept: list[dict] = []

    for evs in by_type.values():
        evs_sorted = sorted(evs, key=lambda e: e["event_time"])
        last_time = None
        for ev in evs_sorted:
            t = _parse_iso(ev["event_time"])
            if last_time is None or (t - last_time).total_seconds() > window_sec:
                kept.append(ev)
                last_time = t
            else:
                # В пределах окна:
                #   sleep — оставляем ПОСЛЕДНЕЕ (реальный отбой, а не первое нажатие)
                #   wake  — оставляем ПЕРВОЕ (реальный подъём, а не последнее нажатие)
                if ev["event_type"] == "sleep":
                    kept[-1] = ev

    kept.sort(key=lambda e: e["event_time"])
    return kept


def add_sleep_from_web_events(prefs_repo, target_date: str) -> dict:
    """Создаёт активность «Ночной сон» за target_date из web-событий.

    Args:
        prefs_repo: PreferencesRepository
        target_date: 'YYYY-MM-DD' — день, за который создаём сон.

    Возвращает dict:
        {"ok": bool, "start": str|None, "end": str|None,
         "duration": int|None, "processed": int, "errors": [str]}
    """
    result = {
        "ok": False,
        "start": None,
        "end": None,
        "duration": None,
        "processed": 0,
        "errors": [],
    }

    # 0. Обязательные настройки — падаем с ошибкой, если нет
    try:
        H = _require_int_pref(prefs_repo, "web_events_sleep_window_start_hour")
        window_sec = _require_int_pref(prefs_repo, "web_events_dedupe_window_sec")
    except ValueError as e:
        result["errors"].append(str(e))
        return result

    # 1. Окно [D-1 H:00, D H:00)
    dt_D = datetime.strptime(target_date, "%Y-%m-%d")
    dt_D_minus_1 = dt_D - timedelta(days=1)
    start_naive = dt_D_minus_1.replace(hour=H, minute=0, second=0, microsecond=0)
    end_naive = dt_D.replace(hour=H, minute=0, second=0, microsecond=0)

    start_window_iso = start_naive.replace(tzinfo=datetime_utils._USER_TZ).isoformat()
    end_window_iso = end_naive.replace(tzinfo=datetime_utils._USER_TZ).isoformat()

    db = prefs_repo.db
    events_repo = WebTimeEventsRepository(db)
    activities_repo = ActivitiesRepository(db)
    types_repo = ActivityTypesRepository(db)

    # 2. Необработанные события в окне
    rows = events_repo.get_unprocessed_in_range(start_window_iso, end_window_iso)
    if not rows:
        msg = (
            f"Нет необработанных web-событий в окне "
            f"[{start_window_iso}, {end_window_iso})"
        )
        # Подсказка: возможно, выбрана не та дата. Покажем необработанные
        # события вне окна, если они есть.
        all_rows = events_repo.get_all()
        unprocessed_elsewhere = [
            {"id": r[0], "server_event_id": r[1], "event_type": r[2], "event_time": r[3]}
            for r in all_rows if r[4] == 0
        ]
        if unprocessed_elsewhere:
            msg += "\n" + _format_events_list(
                unprocessed_elsewhere,
                "Необработанные события вне окна:"
            )
        result["errors"].append(msg)
        return result

    events = [
        {"id": r[0], "server_event_id": r[1], "event_type": r[2], "event_time": r[3]}
        for r in rows
    ]

    # 3. Предпроверка: события каждого типа должны укладываться в окно
    for etype in ("sleep", "wake"):
        err = _check_events_fit_window(events, etype, window_sec)
        if err:
            result["errors"].append(err)
            return result

    # 4. Дедупликация
    kept = _dedupe(events, window_sec)

    # 5. Последний sleep, первый wake после него
    sleeps = [e for e in kept if e["event_type"] == "sleep"]
    wakes = [e for e in kept if e["event_type"] == "wake"]

    if not sleeps:
        msg = "Нет событий «Отбой» (sleep) в окне."
        msg += "\n" + _format_events_list(events, "Список текущих записей:")
        result["errors"].append(msg)
        return result

    last_sleep = sleeps[-1]
    last_sleep_time = _parse_iso(last_sleep["event_time"])

    wakes_after = [w for w in wakes if _parse_iso(w["event_time"]) > last_sleep_time]
    if not wakes_after:
        msg = f"Нет события «Подъём» (wake) после отбоя {last_sleep['event_time']}."
        msg += "\n" + _format_events_list(events, "Список текущих записей:")
        result["errors"].append(msg)
        return result

    first_wake = wakes_after[0]
    first_wake_time = _parse_iso(first_wake["event_time"])

    # 6. Явная проверка end > start
    if first_wake_time <= last_sleep_time:
        msg = (
            f"Подъём ({first_wake['event_time']}) должен быть позже отбоя "
            f"({last_sleep['event_time']})."
        )
        msg += "\n" + _format_events_list(events, "Список текущих записей:")
        result["errors"].append(msg)
        return result

    # 7. Проверка: за D ещё нет ночного сна
    conn = db.connect()
    try:
        existing = conn.execute(
            "SELECT id, start_time, end_time FROM activities "
            "WHERE activity_type_id = :tid AND substr(end_time, 1, 10) = :d "
            "LIMIT 1",
            {"tid": SLEEP_TYPE_ID, "d": target_date}
        ).fetchone()
    finally:
        conn.close()

    if existing:
        result["errors"].append(
            f"За {target_date} уже есть активность «Ночной сон» (id={existing[0]}): "
            f"{existing[1]} — {existing[2]}. Удалите её вручную и повторите."
        )
        return result

    # 8. Дефолтные роль/подроль для типа 1
    types = types_repo.get_all()
    sleep_type = next((t for t in types if t[0] == SLEEP_TYPE_ID), None)
    if not sleep_type:
        result["errors"].append("Тип активности id=1 «Ночной сон» не найден")
        return result
    default_role_id = sleep_type[3]
    default_sub_id = sleep_type[4]

    # 9. Создать активность
    start_iso = last_sleep["event_time"]
    end_iso = first_wake["event_time"]
    duration_min = int((first_wake_time - last_sleep_time).total_seconds() / 60)

    try:
        activities_repo.add(
            type_id=SLEEP_TYPE_ID,
            role_id=default_role_id,
            sub_role_id=default_sub_id,
            start_time=start_iso,
            end_time=end_iso,
            duration=duration_min,
            clean_duration=duration_min,
            breaks_duration=0,
            engagement=100,
            is_estimated=0,
            source="web_events",
            notes=(
                f"создан из web-событий "
                f"(отбой id={last_sleep['server_event_id']}, "
                f"подъём id={first_wake['server_event_id']})"
            ),
            regular_duty_id=None,
        )
    except Exception as e:
        logger.exception("add_sleep_from_web_events: insert failed")
        result["errors"].append(f"Не удалось создать активность: {e}")
        return result

    result["start"] = start_iso
    result["end"] = end_iso
    result["duration"] = duration_min

    # 10. Пометить ВСЕ события в окне как обработанные
    all_ids = [e["id"] for e in events]
    try:
        events_repo.mark_processed(all_ids)
        result["processed"] = len(all_ids)
    except Exception as e:
        logger.exception("add_sleep_from_web_events: mark_processed failed")
        result["errors"].append(
            f"Не удалось пометить события {all_ids}: {e}"
        )

    result["ok"] = len(result["errors"]) == 0
    return result