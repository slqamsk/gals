# src/score_calculator.py
# Класс для математического расчета оценок (Score) на основе фактов и целей.

from .constants import GoalType, ValueType


class ScoreCalculator:

    @staticmethod
    def calculate_score(indicator: dict, actual_value: str) -> float:
        """Считает итоговый процент (0-100) для одного индикатора."""

        if not actual_value or str(actual_value).strip() == "":
            return 0.0

        # 1. Парсим факт в зависимости от value_type
        try:
            if indicator["value_type"] == ValueType.NUMBER.value:
                fact = float(actual_value)
            elif indicator["value_type"] == ValueType.TIME.value:
                fact = ScoreCalculator._parse_time_to_minutes(actual_value)
            elif indicator["value_type"] == ValueType.TIME_OVERNIGHT.value:
                fact = ScoreCalculator._parse_time_to_minutes(actual_value, overnight=True)
            elif indicator["value_type"] == ValueType.BOOLEAN.value:
                fact = 1.0 if str(actual_value).lower() in ["1", "true", "да"] else 0.0
            else:
                fact = float(actual_value)
        except ValueError:
            return 0.0  # Если не смогли распарсить, ставим 0%

        goal_type = indicator["goal_type"]
        step = float(indicator["goal_step"] or 0)
        penalty_per_step = float(indicator["goal_penalty"] or 0)

        # 2. Для BINARY цель не требуется — выходим до парсинга target_value
        if goal_type == GoalType.BINARY.value:
            return 100.0 if fact > 0 else 0.0

        # 3. Парсим цель (только для типов, где она имеет смысл)
        if indicator["value_type"] == ValueType.NUMBER.value:
            target = float(indicator["target_value"])
        elif indicator["value_type"] in (ValueType.TIME.value, ValueType.TIME_OVERNIGHT.value):
            target = ScoreCalculator._parse_time_to_minutes(
                indicator["target_value"],
                overnight=(indicator["value_type"] == ValueType.TIME_OVERNIGHT.value)
            )
        else:
            # BOOLEAN с не-BINARY целью — неопределённое поведение
            return 0.0

        # 4. Считаем оценку по типу цели
        deviation = 0.0

        if goal_type == GoalType.MAXIMIZE.value:
            if fact >= target:
                return 100.0
            deviation = target - fact

        elif goal_type == GoalType.MINIMIZE.value:
            if fact <= target:
                return 100.0
            deviation = fact - target

        elif goal_type == GoalType.TARGET.value:
            deviation = abs(fact - target)

        # 5. Применяем штраф
        if step > 0:
            steps = deviation / step
            penalty = steps * penalty_per_step
            score = 100.0 - penalty
            return max(0.0, score)  # Оценка не может быть меньше 0
        else:
            # Если шаг не задан, но цель есть, делаем простую пропорцию
            if goal_type == GoalType.MINIMIZE.value and fact > 0:
                return min(100.0, (target / fact) * 100.0)
            elif target > 0:
                return min(100.0, (fact / target) * 100.0)
            return 100.0 if fact == target else 0.0

    @staticmethod
    def _parse_time_to_minutes(time_str: str, overnight: bool = False) -> float:
        """Переводит '22:00' в минуты. Если overnight=True, то 03:00 станет 27:00 (1620 минут)."""
        time_str = str(time_str).strip()
        if ":" not in time_str:
            raise ValueError("Время должно быть в формате ЧЧ:ММ")

        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])

        total_minutes = hours * 60 + minutes

        # Если это ночное время (например, отбой) и час меньше 12, значит это следующий день
        if overnight and hours < 12:
            total_minutes += 24 * 60

        return float(total_minutes)