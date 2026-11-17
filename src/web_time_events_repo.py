# src/web_time_events_repo.py
# Репозиторий для работы с событиями «Подъём»/«Отбой», синхронизированными
# с веб-API (slqa.ru/z/api).

from .database import Database


class WebTimeEventsRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, server_event_id: int, event_type: str, event_time: str,
            created_at: str) -> int | None:
        """INSERT OR IGNORE по server_event_id.

        Returns:
            id новой строки, если вставка произошла;
            None, если событие с таким server_event_id уже было.
        """
        conn = self.db.connect()
        try:
            cur = conn.execute(
                "INSERT OR IGNORE INTO web_time_events "
                "(server_event_id, event_type, event_time, created_at) "
                "VALUES (:sid, :etype, :etime, :created)",
                {
                    "sid": server_event_id,
                    "etype": event_type,
                    "etime": event_time,
                    "created": created_at,
                }
            )
            conn.commit()
            if cur.rowcount > 0:
                return cur.lastrowid
            return None
        finally:
            conn.close()

    def get_all(self) -> list[tuple]:
        """Все события: (id, server_event_id, event_type, event_time,
        processed, created_at, updated_at). Свежие — первыми."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, server_event_id, event_type, event_time, "
                "processed, created_at, updated_at "
                "FROM web_time_events "
                "ORDER BY event_time DESC, id DESC"
            ).fetchall()
        finally:
            conn.close()

    def get_unprocessed_in_range(self, start_iso: str, end_iso: str) -> list[tuple]:
        """Необработанные события в полуинтервале [start_iso, end_iso):
        (id, server_event_id, event_type, event_time).
        Сортировка по event_time ASC — для алгоритма сна."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, server_event_id, event_type, event_time "
                "FROM web_time_events "
                "WHERE processed = 0 "
                "AND event_time >= :start "
                "AND event_time <  :end "
                "ORDER BY event_time ASC, id ASC",
                {"start": start_iso, "end": end_iso}
            ).fetchall()
        finally:
            conn.close()

    def mark_all_unprocessed(self) -> list[tuple]:
        """Помечает ВСЕ необработанные события как processed=1.

        Возвращает список полных записей помеченных событий (для лога):
            [(id, server_event_id, event_type, event_time), ...]
        Сортировка по id.
        """
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id, server_event_id, event_type, event_time "
                "FROM web_time_events WHERE processed = 0 ORDER BY id"
            ).fetchall()
            if not rows:
                return []
            conn.execute(
                "UPDATE web_time_events SET processed = 1 WHERE processed = 0"
            )
            conn.commit()
            return [tuple(r) for r in rows]
        finally:
            conn.close()

    def get_unprocessed_count(self) -> int:
        """Сколько необработанных событий (для UI)."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM web_time_events WHERE processed = 0"
            ).fetchone()[0]
        finally:
            conn.close()

    def mark_processed(self, ids: list[int]):
        """Помечает события как обработанные (processed = 1)."""
        if not ids:
            return
        conn = self.db.connect()
        try:
            placeholders = ",".join([":id" + str(i) for i in range(len(ids))])
            params = {"id" + str(i): v for i, v in enumerate(ids)}
            conn.execute(
                f"UPDATE web_time_events SET processed = 1 WHERE id IN ({placeholders})",
                params
            )
            conn.commit()
        finally:
            conn.close()