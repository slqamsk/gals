# src/period_repo.py
# Репозиторий для работы со справочником периодов.

from datetime import datetime, timedelta
import calendar
from .database import Database
from .constants import MetricType


class PeriodRepository:
    def __init__(self, db: Database):
        self.db = db

    def get_or_create(self, period_type: MetricType, target_date: str) -> int:
        """Находит ID периода, в который попадает дата, или создает новый.

        Для DAY фактические границы рассчитываются из ночного сна.
        Для WEEK/MONTH — по умолчанию календарные (пн 00:00 — вс 23:59:59,
        1-е 00:00 — последнее 23:59:59). Позже могут быть уточнены
        через refresh_aggregate_bounds() на основе существующих day-периодов.
        """
        if not isinstance(period_type, MetricType):
            raise ValueError(f"КРИТИЧЕСКАЯ ОШИБКА: Недопустимый тип периода '{period_type}'")

        dt = datetime.strptime(target_date, "%Y-%m-%d")

        if period_type == MetricType.DAY:
            period_value = target_date
            start_date = target_date
            end_date = target_date
            fact_start, fact_end = self._calc_day_bounds(target_date)

        elif period_type == MetricType.WEEK:
            start_of_week = dt - timedelta(days=dt.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            period_value = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
            start_date = start_of_week.strftime("%Y-%m-%d")
            end_date = end_of_week.strftime("%Y-%m-%d")
            fact_start = f"{start_date}T00:00:00+03:00"
            fact_end = f"{end_date}T23:59:59+03:00"

        elif period_type == MetricType.MONTH:
            last_day = calendar.monthrange(dt.year, dt.month)[1]
            period_value = dt.strftime("%Y-%m")
            start_date = dt.replace(day=1).strftime("%Y-%m-%d")
            end_date = dt.replace(day=last_day).strftime("%Y-%m-%d")
            fact_start = f"{start_date}T00:00:00+03:00"
            fact_end = f"{end_date}T23:59:59+03:00"

        else:
            raise ValueError(f"КРИТИЧЕСКАЯ ОШИБКА: Для типа '{period_type}' не написана логика вычисления дат.")

        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT id FROM periods WHERE period_type = :ptype AND :tdate BETWEEN start_date AND end_date",
                {"ptype": period_type.value, "tdate": target_date}
            ).fetchone()

            if row:
                # Для DAY пересчитываем фактические границы (могли измениться после добавления сна).
                if period_type == MetricType.DAY:
                    conn.execute(
                        "UPDATE periods SET fact_start = :fs, fact_end = :fe WHERE id = :pid",
                        {"fs": fact_start, "fe": fact_end, "pid": row[0]}
                    )
                    conn.commit()
                return row[0]

            cursor = conn.execute(
                "INSERT INTO periods (period_type, period_value, start_date, end_date, fact_start, fact_end) "
                "VALUES (:ptype, :pvalue, :sdate, :edate, :fs, :fe)",
                {
                    "ptype": period_type.value,
                    "pvalue": period_value,
                    "sdate": start_date,
                    "edate": end_date,
                    "fs": fact_start,
                    "fe": fact_end,
                }
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def _calc_day_bounds(self, date_str: str) -> tuple[str, str]:
        """Считает фактические границы дня.

        fact_start = начало самого раннего ночного сна, заканчивающегося в этот день.
                    Если сна нет — 'date_strT00:00:00+03:00'.
        fact_end   = начало ночного сна следующего дня (если он уже занесён в БД),
                    иначе 'date_strT23:59:59+03:00'.
        """
        conn = self.db.connect()
        try:
            sleep = conn.execute(
                "SELECT start_time FROM activities "
                "WHERE activity_type_id = 1 AND substr(end_time, 1, 10) = :d "
                "ORDER BY start_time ASC LIMIT 1",
                {"d": date_str}
            ).fetchone()

            if sleep and sleep[0]:
                fact_start = sleep[0]
            else:
                fact_start = f"{date_str}T00:00:00+03:00"

            next_dt = datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)
            next_str = next_dt.strftime("%Y-%m-%d")
            next_sleep = conn.execute(
                "SELECT start_time FROM activities "
                "WHERE activity_type_id = 1 AND substr(end_time, 1, 10) = :d "
                "ORDER BY start_time ASC LIMIT 1",
                {"d": next_str}
            ).fetchone()

            if next_sleep and next_sleep[0]:
                fact_end = next_sleep[0]
            else:
                fact_end = f"{date_str}T23:59:59+03:00"

            return fact_start, fact_end
        finally:
            conn.close()

    def _get_day_fact_start(self, date_str: str):
        """Возвращает fact_start существующего day-периода или None.

        Не создаёт период. Используется при расчёте границ week/month.
        """
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT fact_start FROM periods "
                "WHERE period_type = 'day' AND period_value = :d",
                {"d": date_str}
            ).fetchone()
            if row and row[0]:
                return row[0]
            return None
        finally:
            conn.close()

    def get_period_meta(self, period_id: int):
        """Возвращает (period_type, period_value, start_date, end_date,
        fact_start, fact_end) или None."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT period_type, period_value, start_date, end_date, fact_start, fact_end "
                "FROM periods WHERE id = :pid",
                {"pid": period_id}
            ).fetchone()
        finally:
            conn.close()

    def get_day_periods_in_range(self, start_date: str, end_date: str) -> list[tuple]:
        """Возвращает day-периоды в диапазоне [start_date, end_date] (по start_date):
        [(period_id, period_value), ...].
        """
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, period_value FROM periods "
                "WHERE period_type = 'day' AND start_date BETWEEN :sd AND :ed "
                "ORDER BY period_value",
                {"sd": start_date, "ed": end_date}
            ).fetchall()
        finally:
            conn.close()

    def get_available_periods(self, period_type: str) -> list[tuple]:
        """Возвращает периоды заданного типа для UI-выбора:
        [(id, period_value, start_date, end_date), ...],
        сначала самые свежие (по end_date DESC).
        """
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, period_value, start_date, end_date FROM periods "
                "WHERE period_type = :ptype "
                "ORDER BY end_date DESC, id DESC",
                {"ptype": period_type}
            ).fetchall()
        finally:
            conn.close()



    def _calc_aggregate_bounds(self, ptype: str, start_date: str, end_date: str):
        """Вычисляет fact_start/fact_end для week/month.

        Правило:
          week:
            fact_start = fact_start(monday), если понедельник существует,
                         иначе monday T00:00:00+03:00;
            fact_end   = fact_start(next monday), если следующий понедельник
                         существует, иначе sunday T23:59:59+03:00.
          month:
            fact_start = fact_start(1st), если 1-е существует,
                         иначе 1st T00:00:00+03:00;
            fact_end   = fact_start(1st of next month), если 1-е следующего
                         месяца существует, иначе last day T23:59:59+03:00.
        """
        if ptype == MetricType.WEEK.value:
            monday_fs = self._get_day_fact_start(start_date)
            new_fs = monday_fs if monday_fs else f"{start_date}T00:00:00+03:00"

            next_monday_dt = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=7)
            next_monday = next_monday_dt.strftime("%Y-%m-%d")
            next_monday_fs = self._get_day_fact_start(next_monday)
            new_fe = next_monday_fs if next_monday_fs else f"{end_date}T23:59:59+03:00"
            return (new_fs, new_fe)

        if ptype == MetricType.MONTH.value:
            first_fs = self._get_day_fact_start(start_date)
            new_fs = first_fs if first_fs else f"{start_date}T00:00:00+03:00"

            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            if end_dt.month == 12:
                next_first_dt = end_dt.replace(year=end_dt.year + 1, month=1, day=1)
            else:
                next_first_dt = end_dt.replace(month=end_dt.month + 1, day=1)
            next_first = next_first_dt.strftime("%Y-%m-%d")
            next_first_fs = self._get_day_fact_start(next_first)
            new_fe = next_first_fs if next_first_fs else f"{end_date}T23:59:59+03:00"
            return (new_fs, new_fe)

        return (None, None)

    def refresh_aggregate_bounds(self, period_id: int):
        """Обновляет fact_start/fact_end для week/month по новой логике.

        Для DAY — ничего не делает (границы рассчитываются в get_or_create).
        """
        meta = self.get_period_meta(period_id)
        if not meta:
            return
        ptype, _pvalue, start_date, end_date, _old_fs, _old_fe = meta

        if ptype == MetricType.DAY.value:
            return

        new_fs, new_fe = self._calc_aggregate_bounds(ptype, start_date, end_date)
        if new_fs is None:
            return

        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE periods SET fact_start = :fs, fact_end = :fe WHERE id = :pid",
                {"fs": new_fs, "fe": new_fe, "pid": period_id}
            )
            conn.commit()
        finally:
            conn.close()

    def refresh_day_bounds_if_exists(self, date_str: str):
        """Пересчитывает fact_start/fact_end для day-периода date_str, если он существует.

        Не создаёт новый период (ленивое создание сохраняется).

        Returns:
            None — если day-период за date_str не существует.
            (old_fact_start, old_fact_end, new_fact_start, new_fact_end) — иначе.
            Границы в БД уже обновлены на new_* (UPDATE выполняется только при
            фактическом изменении значений).
        """
        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT id, fact_start, fact_end FROM periods "
                "WHERE period_type = 'day' AND period_value = :d",
                {"d": date_str}
            ).fetchone()
            if not row:
                return None
            pid, old_fs, old_fe = row
            new_fs, new_fe = self._calc_day_bounds(date_str)
            if new_fs != old_fs or new_fe != old_fe:
                conn.execute(
                    "UPDATE periods SET fact_start = :fs, fact_end = :fe WHERE id = :pid",
                    {"fs": new_fs, "fe": new_fe, "pid": pid}
                )
                conn.commit()
            return (old_fs, old_fe, new_fs, new_fe)
        finally:
            conn.close()

    def refresh_all_day_bounds(self) -> list[dict]:
        """Пересчитывает fact_start/fact_end для всех существующих day-периодов.

        Не создаёт новые периоды. Возвращает список изменений (только те,
        у которых значения действительно поменялись):
            [{"period_value", "old_fact_start", "old_fact_end",
              "new_fact_start", "new_fact_end"}, ...]
        """
        conn = self.db.connect()
        changes = []
        try:
            rows = conn.execute(
                "SELECT id, period_value, fact_start, fact_end FROM periods "
                "WHERE period_type = 'day' ORDER BY period_value"
            ).fetchall()
            for pid, pvalue, old_fs, old_fe in rows:
                new_fs, new_fe = self._calc_day_bounds(pvalue)
                if new_fs != old_fs or new_fe != old_fe:
                    conn.execute(
                        "UPDATE periods SET fact_start = :fs, fact_end = :fe WHERE id = :pid",
                        {"fs": new_fs, "fe": new_fe, "pid": pid}
                    )
                    changes.append({
                        "period_value": pvalue,
                        "old_fact_start": old_fs,
                        "old_fact_end": old_fe,
                        "new_fact_start": new_fs,
                        "new_fact_end": new_fe,
                    })
            conn.commit()
            return changes
        finally:
            conn.close()

    def refresh_all_aggregate_bounds(self) -> list[dict]:
        """Пересчитывает fact_start/fact_end для всех week/month по новой логике.

        Возвращает список изменений:
            [{"period_type": "week"|"month", "period_value",
              "old_fact_start", "old_fact_end",
              "new_fact_start", "new_fact_end"}, ...]
        """
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id, period_type, period_value, start_date, end_date, "
                "fact_start, fact_end FROM periods "
                "WHERE period_type IN ('week', 'month') "
                "ORDER BY period_type, period_value"
            ).fetchall()
        finally:
            conn.close()

        changes = []
        for pid, ptype, pvalue, start_date, end_date, old_fs, old_fe in rows:
            new_fs, new_fe = self._calc_aggregate_bounds(ptype, start_date, end_date)
            if new_fs is None:
                continue
            if new_fs != old_fs or new_fe != old_fe:
                conn = self.db.connect()
                try:
                    conn.execute(
                        "UPDATE periods SET fact_start = :fs, fact_end = :fe WHERE id = :pid",
                        {"fs": new_fs, "fe": new_fe, "pid": pid}
                    )
                    conn.commit()
                finally:
                    conn.close()
                changes.append({
                    "period_type": ptype,
                    "period_value": pvalue,
                    "old_fact_start": old_fs,
                    "old_fact_end": old_fe,
                    "new_fact_start": new_fs,
                    "new_fact_end": new_fe,
                })
        return changes