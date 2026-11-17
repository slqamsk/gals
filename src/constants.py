# src/constants.py
# Системные константы и перечисления (Enum).

from enum import Enum


class MetricType(str, Enum):
    """Допустимые типы метрик и их циклы расчета."""
    DAY = "day"           # Ежедневная метрика (период = день)
    WEEK = "week"         # Еженедельная метрика (период = неделя)
    MONTH = "month"       # Ежемесячная метрика (период = месяц)
    MANUAL = "manual"     # Ручная метрика (без автоматического расчета)


class GoalType(str, Enum):
    """Типы целей для индикаторов."""
    MAXIMIZE = "maximize"    # Больше - лучше (100% при достижении цели)
    MINIMIZE = "minimize"    # Меньше - лучше (100% при достижении цели)
    TARGET = "target"        # Точное значение (Колокол: штраф за отклонение в обе стороны)
    BINARY = "binary"        # Да/Нет (100% если факт > 0, иначе 0%)


class ValueType(str, Enum):
    """Типы значений, которые возвращает калькулятор, и правила их парсинга."""
    NUMBER = "number"              # Обычное число (480, 10000)
    TIME = "time"                  # Время в сутках (08:30)
    TIME_OVERNIGHT = "time_overnight"  # Время вечера/ночи (03:00 ночи = 27:00 для расчетов)
    BOOLEAN = "boolean"            # Флаг Да/Нет (1 или 0)


class CalcMethod(str, Enum):
    """Доступные методы в Python для извлечения данных из активности
    или из отметок регулярной обязанности, или из ответов на вопросы."""
    DURATION = "calc_duration"         # Длительность (end - start). Для индикаторов по типу активности
    START_TIME = "calc_start_time"     # Время начала (отбой, подъем). По типу активности
    COUNT = "calc_count"               # Количество раз. По типу активности
    DUTY_DONE = "calc_duty_done"       # 1, если последняя отметка обязанности = done, иначе 0. Для BINARY
    DUTY_MARK = "calc_duty_mark"       # mark_value последней отметки обязанности (0..100). Для MAXIMIZE/TARGET
    QUESTION_LAST = "calc_question_last"  # value последнего ответа на вопрос за период (0..100). Для MAXIMIZE/TARGET


class AffectAxis(str, Enum):
    """Ось графика, на которую влияет индикатор."""
    SATISFACTION = "satisfaction"   # Удовлетворённость результатом (ось X)
    ATTENTION = "attention"         # Вложение усилий (ось Y)