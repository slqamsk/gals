# src/regular_duty_marks_repo.py
# Репозиторий для работы с отметками о выполнении регулярных обязанностей.

from .database import Database


class RegularDutyMarksRepository:
    # Управляет чтением и записью отметок в таблицу regular_duty_marks.
    def __init__(self, db: Database):
        self.db = db

    def get_for_period(self, duty_id: int, period_id: int) -> list[tuple]:
        """Все отметки обязанности за период (id, status, mark_value,
        marked_at, note, created_at), свежие — первыми."""
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id, status, mark_value, marked_at, note, created_at "
                "FROM regular_duty_marks "
                "WHERE duty_id = :did AND period_id = :pid "
                "ORDER BY marked_at DESC",
                {"did": duty_id, "pid": period_id}
            ).fetchall()
        finally:
            conn.close()
        return rows

    def get_all_for_period(self, period_id: int) -> dict[int, dict]:
        """Последняя отметка по каждой обязанности за период.

        Возвращает {duty_id: {"status", "mark_value", "marked_at", "note"}}.
        Если у обязанности несколько отметок за период — берётся та,
        у которой marked_at максимальный.
        """
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT rdm.duty_id, rdm.status, rdm.mark_value, rdm.marked_at, rdm.note "
                "FROM regular_duty_marks rdm "
                "JOIN ("
                "    SELECT duty_id, MAX(marked_at) AS max_marked_at "
                "    FROM regular_duty_marks WHERE period_id = :pid GROUP BY duty_id"
                ") latest ON rdm.duty_id = latest.duty_id "
                "        AND rdm.marked_at = latest.max_marked_at "
                "WHERE rdm.period_id = :pid",
                {"pid": period_id}
            ).fetchall()
        finally:
            conn.close()
        return {
            row[0]: {
                "status": row[1],
                "mark_value": row[2],
                "marked_at": row[3],
                "note": row[4],
            }
            for row in rows
        }

    def add(self, duty_id: int, period_id: int, marked_at: str,
            status: str, mark_value: int, note: str | None = None):
        """Добавляет отметку. CHECK в БД гарантирует согласованность
        status ↔ mark_value."""
        conn = self.db.connect()
        try:
            conn.execute(
                "INSERT INTO regular_duty_marks "
                "(duty_id, period_id, marked_at, status, mark_value, note) "
                "VALUES (:did, :pid, :marked_at, :status, :mark_value, :note)",
                {
                    "did": duty_id,
                    "pid": period_id,
                    "marked_at": marked_at,
                    "status": status,
                    "mark_value": mark_value,
                    "note": note,
                }
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, mark_id: int):
        """Удаляет конкретную отметку по id."""
        conn = self.db.connect()
        try:
            conn.execute(
                "DELETE FROM regular_duty_marks WHERE id = :id",
                {"id": mark_id}
            )
            conn.commit()
        finally:
            conn.close()

    def delete_all_for_period(self, duty_id: int, period_id: int):
        """Снимает все отметки обязанности за период («снять отметку»)."""
        conn = self.db.connect()
        try:
            conn.execute(
                "DELETE FROM regular_duty_marks WHERE duty_id = :did AND period_id = :pid",
                {"did": duty_id, "pid": period_id}
            )
            conn.commit()
        finally:
            conn.close()