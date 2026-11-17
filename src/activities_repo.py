# src/activities_repo.py
# Репозиторий для работы с фактами активностей.

from . import datetime_utils
from .database import Database


class ActivitiesRepository:
    # Управляет чтением и записью активностей.
    def __init__(self, db: Database):
        self.db = db

    # Возвращает список активностей с расшифровкой имен.
    # Если передан target_date (YYYY-MM-DD), возвращает только активности за этот день
    # (с учётом фактических границ GALS fact_start/fact_end, а не просто календарных суток).
    # Пустые активности (без start_time) показываются при любой дате.
    # Порядок колонок:
    #   0  a.id
    #   1  at.name       (тип активности)
    #   2  rd.name       (обязанность, может быть NULL)
    #   3  r.name        (роль)
    #   4  sr.name       (под-роль)
    #   5  a.start_time
    #   6  a.end_time
    #   7  a.duration
    #   8  a.clean_duration
    #   9  a.breaks_duration
    #   10 a.engagement_percentage
    #   11 a.is_estimated
    #   12 a.source
    #   13 a.notes
    #   14 a.created_at
    #   15 a.updated_at
    #   16 a.regular_duty_id
    def get_all(self, target_date: str | None = None) -> list[tuple]:
        conn = self.db.connect()
        try:
            query = (
                "SELECT a.id, at.name, rd.name, r.name, sr.name, "
                "a.start_time, a.end_time, "
                "a.duration, a.clean_duration, a.breaks_duration, a.engagement_percentage, "
                "a.is_estimated, a.source, a.notes, a.created_at, a.updated_at, "
                "a.regular_duty_id "
                "FROM activities a "
                "JOIN activity_types at ON a.activity_type_id = at.id "
                "LEFT JOIN roles r ON a.role_id = r.id "
                "LEFT JOIN sub_roles sr ON a.sub_role_id = sr.id "
                "LEFT JOIN regular_duties rd ON a.regular_duty_id = rd.id "
            )

            params = {}
            if target_date:
                # Пытаемся взять фактические границы дня из periods (GALS-день)
                period_row = conn.execute(
                    "SELECT fact_start, fact_end FROM periods WHERE period_type='day' AND period_value=:d",
                    {"d": target_date}
                ).fetchone()

                if period_row and period_row[0] and period_row[1]:
                    fs = period_row[0]
                    fe = period_row[1]
                else:
                    # Если периода еще нет (например, за этот день не вносили сон),
                    # берем календарные сутки
                    fs = f"{target_date}T00:00:00+03:00"
                    fe = f"{target_date}T23:59:59+03:00"

                # Пустые активности (без start_time) показываются при любой дате
                query += (
                    "WHERE (a.start_time IS NULL OR a.start_time = '' "
                    "OR (a.start_time >= :fs AND a.start_time < :fe)) "
                )
                params = {"fs": fs, "fe": fe}

            query += "ORDER BY a.start_time DESC"

            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        return rows

    # Возвращает максимальный end_time среди всех активностей (ISO 8601) или None.
    # Используется в диалоге «Добавить активность» — время начала по умолчанию.
    def get_max_end_time(self) -> str | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT MAX(end_time) FROM activities WHERE end_time IS NOT NULL"
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row and row[0] else None

    # Возвращает максимальный end_time среди активностей, закончившихся в date_str.
    # Для предзаполнения «начало» в диалоге «Добавить активность» (Ручная работа).
    def get_max_end_time_for_date(self, date_str: str) -> str | None:
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT MAX(end_time) FROM activities "
                "WHERE end_time IS NOT NULL AND substr(end_time, 1, 10) = :d",
                {"d": date_str}
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row and row[0] else None

    # Полная запись активности по id (для диалога редактирования в
    # «Выполнении обязанностей»). Возвращает кортеж из 14 колонок.
    def get_by_id(self, act_id: int) -> tuple | None:
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, activity_type_id, role_id, sub_role_id, "
                "start_time, end_time, duration, clean_duration, breaks_duration, "
                "engagement_percentage, is_estimated, source, notes, regular_duty_id "
                "FROM activities WHERE id = :id",
                {"id": act_id}
            ).fetchone()
        finally:
            conn.close()

    # Возвращает активности указанной обязанности в полуинтервале [fact_start, fact_end).
    # Для вкладки «Выполнение обязанностей».
    def get_by_duty_and_period(self, duty_id: int, fact_start: str, fact_end: str) -> list[tuple]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id, start_time, end_time, duration, notes "
                "FROM activities "
                "WHERE regular_duty_id = :did "
                "AND start_time >= :fs AND start_time < :fe "
                "ORDER BY start_time",
                {"did": duty_id, "fs": fact_start, "fe": fact_end}
            ).fetchall()
        finally:
            conn.close()
        return rows

    # Добавляет новую активность.
    # regular_duty_id — в конце, по умолчанию None (чтобы старые вызовы не ломались).
    # created_at — если None, подставляется текущее время.
    # Секунды обнуляются (MVP: минутная точность).
    def add(self, type_id: int, role_id: int | None, sub_role_id: int | None, 
            start_time: str, end_time: str | None,
            duration: int | None, clean_duration: int | None,
            breaks_duration: int | None, engagement: int | None,
            is_estimated: int, source: str, notes: str,
            regular_duty_id: int | None = None,
            created_at: str | None = None):
        # MVP: минутная точность — секунды обнуляем на границе записи.
        start_time = datetime_utils.to_minute_iso(start_time)
        end_time = datetime_utils.to_minute_iso(end_time)
        # Если created_at не передан явно (импорт, восстановление) — берём текущее время.
        if created_at is None:
            created_at = datetime_utils.get_now_iso()
        conn = self.db.connect()
        try:
            conn.execute(
                "INSERT INTO activities (activity_type_id, role_id, sub_role_id, start_time, end_time, "
                "duration, clean_duration, breaks_duration, engagement_percentage, is_estimated, source, notes, "
                "regular_duty_id, created_at) "
                "VALUES (:type_id, :role_id, :sub_role_id, :start_time, :end_time, "
                ":duration, :clean_duration, :breaks_duration, :engagement, :is_estimated, :source, :notes, "
                ":regular_duty_id, :created_at)",
                {
                    "type_id": type_id,
                    "role_id": role_id,
                    "sub_role_id": sub_role_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "clean_duration": clean_duration,
                    "breaks_duration": breaks_duration,
                    "engagement": engagement,
                    "is_estimated": is_estimated,
                    "source": source,
                    "notes": notes,
                    "regular_duty_id": regular_duty_id,
                    "created_at": created_at,
                }
            )
            conn.commit()
        finally:
            conn.close()

    # Обновляет существующую активность.
    # regular_duty_id — в конце, по умолчанию None.
    # Секунды обнуляются (MVP: минутная точность).
    def update(self, act_id: int, type_id: int, role_id: int | None, sub_role_id: int | None,
               start_time: str, end_time: str | None,
               duration: int | None, clean_duration: int | None,
               breaks_duration: int | None, engagement: int | None,
               is_estimated: int, source: str, notes: str,
               regular_duty_id: int | None = None):
        # MVP: минутная точность — секунды обнуляем на границе записи.
        start_time = datetime_utils.to_minute_iso(start_time)
        end_time = datetime_utils.to_minute_iso(end_time)
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE activities SET "
                "activity_type_id = :type_id, role_id = :role_id, sub_role_id = :sub_role_id, "
                "start_time = :start_time, end_time = :end_time, "
                "duration = :duration, clean_duration = :clean_duration, "
                "breaks_duration = :breaks_duration, engagement_percentage = :engagement, "
                "is_estimated = :is_estimated, source = :source, notes = :notes, "
                "regular_duty_id = :regular_duty_id "
                "WHERE id = :id",
                {
                    "id": act_id,
                    "type_id": type_id,
                    "role_id": role_id,
                    "sub_role_id": sub_role_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "clean_duration": clean_duration,
                    "breaks_duration": breaks_duration,
                    "engagement": engagement,
                    "is_estimated": is_estimated,
                    "source": source,
                    "notes": notes,
                    "regular_duty_id": regular_duty_id,
                }
            )
            conn.commit()
        finally:
            conn.close()

    # Удаляет активность.
    def delete(self, act_id: int):
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM activities WHERE id = ?", (act_id,))
            conn.commit()
        finally:
            conn.close()