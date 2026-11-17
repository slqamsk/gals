# src/indicator_service.py
# Сервис для пересчета индикаторов и сохранения их в историю.

import logging
from datetime import datetime, timedelta

from .indicator_calculator import IndicatorCalculator
from .score_calculator import ScoreCalculator
from .period_repo import PeriodRepository
from .indicator_repo import IndicatorRepository
from .metrics_repo import MetricsRepository
from . import datetime_utils
from .constants import MetricType


logger = logging.getLogger(__name__)


class IndicatorService:
    def __init__(self, db):
        self.db = db
        self.calculator = IndicatorCalculator(db)
        self.period_repo = PeriodRepository(db)
        self.indicator_repo = IndicatorRepository(db)
        self.metrics_repo = MetricsRepository(db)

    def _validate_before_calculate(self, date_str: str):
        """Fail-Fast проверки перед пересчётом day(X).

        - Тип активности id=1 «Ночной сон» существует и назван правильно.
        - Есть ночной сон, заканчивающийся в date_str.
        - Никакая другая активность не пересекается с ночным сном.
        """
        conn = self.db.connect()
        try:
            # 1. Тип "Ночной сон"
            row = conn.execute(
                "SELECT name FROM activity_types WHERE id = 1"
            ).fetchone()
            if not row:
                raise ValueError(
                    "Отсутствует тип активности id=1 «Ночной сон». "
                    "Восстановите его в БД (или пересоздайте базу)."
                )
            if row[0] != "Ночной сон":
                raise ValueError(
                    f"Тип активности id=1 переименован в «{row[0]}». "
                    f"Ожидается «Ночной сон»."
                )

            # 2. Есть сон, заканчивающийся в date_str (берём самый ранний, если их несколько)
            sleep = conn.execute(
                "SELECT id, start_time, end_time FROM activities "
                "WHERE activity_type_id = 1 AND substr(end_time, 1, 10) = :d "
                "ORDER BY start_time ASC LIMIT 1",
                {"d": date_str}
            ).fetchone()

            if not sleep:
                raise ValueError(
                    f"За {date_str} не найден ночной сон. "
                    f"Сначала занесите ночной сон, затем запускайте расчёт."
                )

            sleep_id, sleep_start, sleep_end = sleep

            # 3. Никакая другая активность не пересекается с ночным сном
            conflict = conn.execute(
                "SELECT id, start_time, end_time FROM activities "
                "WHERE id != :sid "
                "AND start_time < :se AND end_time > :ss "
                "LIMIT 1",
                {"sid": sleep_id, "ss": sleep_start, "se": sleep_end}
            ).fetchone()

            if conflict:
                raise ValueError(
                    f"Активность id={conflict[0]} ({conflict[1]} — {conflict[2]}) "
                    f"пересекается с ночным сном (id={sleep_id}). "
                    f"Устраните пересечение и повторите расчёт."
                )
        finally:
            conn.close()

    def _validate_day(self, date_str: str) -> tuple[bool, str]:
        """Обёртка над _validate_before_calculate: (ok, reason) без исключений."""
        try:
            self._validate_before_calculate(date_str)
            return (True, "")
        except Exception as e:
            return (False, str(e))

    def _validate_aggregate(self, period_id: int) -> tuple[bool, str]:
        """Проверяет, можно ли считать индикаторы для week/month-периода.

        Правила:
        - Если внутри нет ни одного day-периода → False.
        - Если хотя бы один существующий day-период невалиден → False.
        - Иначе True.
        """
        meta = self.period_repo.get_period_meta(period_id)
        if not meta:
            return (False, "не удалось получить метаданные периода")
        _ptype, _pvalue, start_date, end_date, _fs, _fe = meta

        day_periods = self.period_repo.get_day_periods_in_range(start_date, end_date)
        if not day_periods:
            return (False, f"нет ни одного day-периода в диапазоне {start_date}..{end_date}")

        for _day_pid, day_value in day_periods:
            ok, reason = self._validate_day(day_value)
            if not ok:
                return (False, f"день {day_value}: {reason}")
        return (True, "")

    def _calculate_period(self, period_type: MetricType, period_id: int):
        """Считает индикаторы, чья метрика имеет указанный metric_type,
        и сохраняет indicator_values + metric_values для данного периода.

        Индикаторы разделяются по оси (affects): satisfaction / attention.
        Для каждой оси — своё средневзвешенное. Если индикаторов на ось нет —
        соответствующее поле metric_values = 0.0.
        """
        indicators = self.indicator_repo.get_all()
        metrics = self.metrics_repo.get_all_metrics()
        metric_by_id = {m["id"]: m for m in metrics}

        # Фильтр: только индикаторы, принадлежащие метрикам нужного типа
        filtered = [
            ind for ind in indicators
            if metric_by_id.get(ind["metric_id"], {}).get("type") == period_type.value
        ]

        # metric_id -> {"satisfaction": [(score, weight), ...],
        #               "attention":    [(score, weight), ...]}
        metric_scores: dict[int, dict[str, list[tuple[float, int]]]] = {}

        for ind in filtered:
            actual_val = self.calculator.calculate_indicator(ind, period_id)
            actual_val_str = "" if actual_val is None else str(actual_val)

            self.indicator_repo.save_value(
                indicator_id=ind["id"],
                period_id=period_id,
                actual_value=actual_val_str,
                created_at=datetime_utils.get_now_iso()
            )

            score = ScoreCalculator.calculate_score(ind, actual_val_str)
            m_id = ind["metric_id"]
            affects = ind.get("affects") or "satisfaction"
            if m_id not in metric_scores:
                metric_scores[m_id] = {"satisfaction": [], "attention": []}
            weight = ind["weight"] if ind["weight"] is not None else 50
            metric_scores[m_id][affects].append((score, weight))

        for m in metrics:
            if m["type"] != period_type.value:
                continue
            m_id = m["id"]

            # Метрика без индикаторов тоже получает строку metric_values (0/0),
            # чтобы присутствовать на графике, а не исчезать из него.
            scores = metric_scores.get(m_id, {"satisfaction": [], "attention": []})
            sat_list = scores["satisfaction"]
            att_list = scores["attention"]

            def _weighted(scores_list):
                if not scores_list:
                    return 0.0
                total_weight = sum(w for _s, w in scores_list)
                if total_weight <= 0:
                    return 0.0
                return sum(s * w for s, w in scores_list) / total_weight

            final_satisfaction = _weighted(sat_list)
            final_attention = _weighted(att_list)

            self.metrics_repo.save_metric_value(
                metric_id=m_id,
                period_id=period_id,
                attention=final_attention,
                satisfaction=final_satisfaction
            )

    def recalculate_for_date(self, date_str):
        """Пересчитывает индикаторы и метрики за date_str.

        Порядок:
          1. Fail-Fast для day(X) — пользователь явно запросил расчёт за X.
          2. Обновить day(X) и day(X−1) (последний — если существует).
          3. Обновить границы week(X), month(X) и, если day(X−1) существует,
             week(X−1), month(X−1).
          4. Пересчитать индикаторы: сначала день, потом недели, потом месяцы.
             day(X) — с Fail-Fast; day(X−1) — тихий пропуск при невалидности.
             week/month — с валидацией (пустой или битый диапазон → skip).

        Returns:
            list[str] — сообщения о результате по каждому периоду (для UI/лога).
        """
        messages = []

        # 0. Fail-Fast: day(X) обязателен
        self._validate_before_calculate(date_str)

        # 1. day(X) — создать/обновить
        period_id_day_X = self.period_repo.get_or_create(MetricType.DAY, date_str)

        # 2. day(X−1) — только если существует
        prev_dt = datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)
        prev_date = prev_dt.strftime("%Y-%m-%d")
        prev_refresh = self.period_repo.refresh_day_bounds_if_exists(prev_date)
        prev_exists = prev_refresh is not None
        prev_period_id_day = None
        if prev_exists:
            prev_period_id_day = self.period_repo.get_or_create(MetricType.DAY, prev_date)

        # 3. week/month X — создать/обновить границы
        week_X_id = self.period_repo.get_or_create(MetricType.WEEK, date_str)
        self.period_repo.refresh_aggregate_bounds(week_X_id)
        month_X_id = self.period_repo.get_or_create(MetricType.MONTH, date_str)
        self.period_repo.refresh_aggregate_bounds(month_X_id)

        # 4. week/month X−1 — если day(X−1) существует
        week_prev_id = None
        month_prev_id = None
        if prev_exists:
            week_prev_id = self.period_repo.get_or_create(MetricType.WEEK, prev_date)
            self.period_repo.refresh_aggregate_bounds(week_prev_id)
            month_prev_id = self.period_repo.get_or_create(MetricType.MONTH, prev_date)
            self.period_repo.refresh_aggregate_bounds(month_prev_id)

        # 5. Пересчёт day(X)
        self._calculate_period(MetricType.DAY, period_id_day_X)
        messages.append(f"day {date_str}: OK")

        # 6. Пересчёт day(X−1) — тихо
        if prev_period_id_day is not None:
            ok, reason = self._validate_day(prev_date)
            if ok:
                self._calculate_period(MetricType.DAY, prev_period_id_day)
                messages.append(f"day {prev_date}: OK")
            else:
                messages.append(f"day {prev_date}: skip — {reason}")
                logger.warning("skip day %s: %s", prev_date, reason)

        # 7. week/month — с валидацией
        targets = [
            (MetricType.WEEK, week_X_id, date_str),
            (MetricType.MONTH, month_X_id, date_str),
        ]
        # Добавляем X−1, если это другой период (например, X — понедельник,
        # тогда week(X−1) — прошлая неделя; если X — вторник, week(X−1)
        # совпадает с week(X), дублировать не нужно).
        if prev_exists and week_prev_id != week_X_id:
            targets.append((MetricType.WEEK, week_prev_id, prev_date))
        if prev_exists and month_prev_id != month_X_id:
            targets.append((MetricType.MONTH, month_prev_id, prev_date))

        for ptype, pid, pdate in targets:
            ok, reason = self._validate_aggregate(pid)
            if ok:
                self._calculate_period(ptype, pid)
                messages.append(f"{ptype.value} {pdate}: OK")
            else:
                messages.append(f"{ptype.value} {pdate}: skip — {reason}")
                logger.warning("skip %s %s: %s", ptype.value, pdate, reason)

        return messages