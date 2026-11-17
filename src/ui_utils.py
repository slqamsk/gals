# src/ui_utils.py
# Общие утилиты для UI (форматирование, отображение, сортировка).

from datetime import datetime


MONTHS_RU = [
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"
]


def format_period_label(mode: str, period: tuple) -> str:
    """Форматирует период для отображения в Combobox.

    Args:
        mode: 'day' | 'week' | 'month'
        period: (period_id, period_value, start_date, end_date)

    Returns:
        - day:   '02.11.26'
        - week:  '2026-W45 (02.11.26–08.11.26)'
        - month: '2026-11 (ноябрь)'
    """
    _pid, period_value, start_date, end_date = period
    if mode == "day":
        try:
            dt = datetime.strptime(period_value, "%Y-%m-%d")
            return dt.strftime("%d.%m.%y")
        except Exception:
            return period_value
    if mode == "week":
        try:
            sd = datetime.strptime(start_date, "%Y-%m-%d")
            ed = datetime.strptime(end_date, "%Y-%m-%d")
            return f"{period_value} ({sd.strftime('%d.%m.%y')}–{ed.strftime('%d.%m.%y')})"
        except Exception:
            return period_value
    if mode == "month":
        try:
            _year, m = period_value.split("-")
            return f"{period_value} ({MONTHS_RU[int(m) - 1]})"
        except Exception:
            return period_value
    return period_value


def sort_sheet_data(rows: list, col: int, asc: bool, numeric_cols: list[int] = None) -> list:
    """Сортирует список строк (для tksheet) по указанной колонке.
    
    None и пустые строки всегда уходят в конец, независимо от направления сортировки.
    """
    if numeric_cols is None:
        numeric_cols = []
        
    valid = []
    invalid = []
    
    for r in rows:
        val = r[col]
        if val is None or str(val).strip() == "":
            invalid.append(r)
        else:
            valid.append(r)
            
    def get_key(r):
        v = r[col]
        if col in numeric_cols:
            try:
                return int(float(v))
            except (ValueError, TypeError):
                return 0
        else:
            return str(v).lower()

    valid.sort(key=get_key, reverse=not asc)
    return valid + invalid