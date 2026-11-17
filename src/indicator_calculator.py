# src/indicator_calculator.py
# Движок для расчета значений индикаторов.

from . import datetime_utils


class IndicatorCalculator:
    # Класс-калькулятор (Стратегия).
    def __init__(self, db):
        self.db = db

    # --- ГЛАВНЫЙ ДИСПЕТЧЕР ---
    def calculate_indicator(self, indicator_row, period_id):
        """indicator_row — dict со всеми полями индикатора,
        включая activity_type_id (может быть None) и regular_duty_id (может быть None).
        Ровно одно из них заполнено (CHECK в БД)."""
        method_name = indicator_row['calc_method']

        if not hasattr(self, method_name):
            raise ValueError(f"Метод '{method_name}' не найден!")

        calc_func = getattr(self, method_name)
        return calc_func(period_id, indicator_row)

    # --- ВСПОМОГАТЕЛЬНЫЙ МЕТОД ---
    def _get_activities(self, period_id, activity_type_id):
        """Получает активности, попадающие в полуинтервал [fact_start, fact_end) периода.

        Принадлежность определяется по start_time активности:
        fact_start <= start_time < fact_end.
        """
        conn = self.db.connect()
        try:
            params = {"per_id": period_id}
            period = conn.execute(
                "SELECT fact_start, fact_end FROM periods WHERE id = :per_id",
                params
            ).fetchone()

            if not period:
                raise ValueError(f"КРИТИЧЕСКАЯ ОШИБКА: Период с ID={period_id} не найден в базе данных!")

            fact_start, fact_end = period
            if not fact_start or not fact_end:
                raise ValueError(
                    f"КРИТИЧЕСКАЯ ОШИБКА: У периода ID={period_id} не рассчитаны fact_start/fact_end."
                )

            act_params = {
                "act_type": activity_type_id,
                "fact_start": fact_start,
                "fact_end": fact_end,
            }
            rows = conn.execute(
                "SELECT * FROM activities "
                "WHERE activity_type_id = :act_type "
                "AND start_time >= :fact_start "
                "AND start_time <  :fact_end "
                "ORDER BY start_time ASC",
                act_params
            ).fetchall()
            return rows
        finally:
            conn.close()

    # --- МЕТОДЫ-КАЛЬКУЛЯТОРЫ ПО ТИПУ АКТИВНОСТИ ---

    def calc_duration(self, period_id, indicator_row):
        """Считает общую длительность (сумма всех действий этого типа)."""
        activity_type_id = indicator_row['activity_type_id']
        if activity_type_id is None:
            return 0

        actions = self._get_activities(period_id, activity_type_id)

        total_minutes = 0
        for action in actions:
            # В таблице activities: id=0, start_time=4, end_time=5 (при SELECT *)
            start_iso = action[4]
            end_iso = action[5]

            if start_iso and end_iso:
                dt_start = datetime_utils.to_datetime(start_iso)
                dt_end = datetime_utils.to_datetime(end_iso)
                diff = dt_end - dt_start
                total_minutes += diff.total_seconds() / 60

        return int(total_minutes)

    def calc_count(self, period_id, indicator_row):
        """Считает количество действий данного типа в периоде.

        Для BINARY-цели достаточно «>0» — реализация сводится к длине
        списка активностей, попавших в полуинтервал [fact_start, fact_end).
        Для MAXIMIZE — это уже количественная оценка («3 прогулки за неделю»).
        """
        activity_type_id = indicator_row['activity_type_id']
        if activity_type_id is None:
            return 0
        actions = self._get_activities(period_id, activity_type_id)
        return len(actions)

    def calc_start_time(self, period_id, indicator_row):
        """Берет время начала самого раннего действия в периоде.

        Возвращает None, если активностей нет или у первой не задан start_time.
        None трактуется выше по стеку как «нет данных» (оценка 0%).
        """
        activity_type_id = indicator_row['activity_type_id']
        if activity_type_id is None:
            return None

        actions = self._get_activities(period_id, activity_type_id)
        if not actions:
            return None

        # Берем первое действие (самое раннее, благодаря ORDER BY start_time ASC)
        start_iso = actions[0][4]
        if start_iso:
            dt = datetime_utils.to_datetime(start_iso)
            return dt.strftime("%H:%M")
        return None


    # --- МЕТОДЫ-КАЛЬКУЛЯТОРЫ ПО ОТВЕТАМ НА ВОПРОСЫ ---

    def calc_question_last(self, period_id, indicator_row):
        """value последнего ответа на вопрос за период (0..100).

        Период задаётся полуинтервалом [fact_start, fact_end) из periods —
        так же, как для активностей.
        Возвращает None, если за период ответов нет.
        """
        question_id = indicator_row.get('question_id')
        if question_id is None:
            return None

        conn = self.db.connect()
        try:
            period = conn.execute(
                "SELECT fact_start, fact_end FROM periods WHERE id = :per_id",
                {"per_id": period_id}
            ).fetchone()
            if not period:
                raise ValueError(
                    f"КРИТИЧЕСКАЯ ОШИБКА: Период с ID={period_id} не найден в базе данных!"
                )
            fact_start, fact_end = period
            if not fact_start or not fact_end:
                raise ValueError(
                    f"КРИТИЧЕСКАЯ ОШИБКА: У периода ID={period_id} не рассчитаны fact_start/fact_end."
                )

            row = conn.execute(
                "SELECT value FROM answers "
                "WHERE question_id = :qid "
                "AND measured_at >= :fs AND measured_at < :fe "
                "ORDER BY measured_at DESC, id DESC LIMIT 1",
                {"qid": question_id, "fs": fact_start, "fe": fact_end}
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None
        return row[0]


    # --- МЕТОДЫ-КАЛЬКУЛЯТОРЫ ПО ОТМЕТКАМ ОБЯЗАННОСТИ ---

    def calc_duty_done(self, period_id, indicator_row):
        """1, если последняя отметка обязанности за период имеет status='done',
        иначе 0 (нет отметки / not_done / partial).

        Для BINARY-индикаторов: «обязанность выполнена полностью — да/нет».
        """
        duty_id = indicator_row['regular_duty_id']
        if duty_id is None:
            return 0

        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT status FROM regular_duty_marks "
                "WHERE duty_id = :did AND period_id = :pid "
                "ORDER BY marked_at DESC, id DESC LIMIT 1",
                {"did": duty_id, "pid": period_id}
            ).fetchone()
        finally:
            conn.close()

        if row and row[0] == 'done':
            return 1
        return 0

    def calc_duty_mark(self, period_id, indicator_row):
        """mark_value последней отметки обязанности за период (0..100).
        Если отметок нет — 0.

        Для MAXIMIZE/TARGET-индикаторов: «насколько выполнена обязанность».
        """
        duty_id = indicator_row['regular_duty_id']
        if duty_id is None:
            return 0

        conn = self.db.connect()
        try:
            row = conn.execute(
                "SELECT mark_value FROM regular_duty_marks "
                "WHERE duty_id = :did AND period_id = :pid "
                "ORDER BY marked_at DESC, id DESC LIMIT 1",
                {"did": duty_id, "pid": period_id}
            ).fetchone()
        finally:
            conn.close()

        if row:
            return row[0]
        return 0