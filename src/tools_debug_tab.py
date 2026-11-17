# src/tools_debug_tab.py
# Вкладка "Служебные операции" (внутри Инструментов).
# Два блока: "Отладка индикаторов" и "Проверить и скорректировать периоды".
# Внизу — общее поле лога.

import tkinter as tk
from datetime import timedelta
from tkcalendar import DateEntry
from . import datetime_utils
from .indicator_service import IndicatorService
from .period_repo import PeriodRepository


class ToolsDebugTab(tk.Frame):
    # Вкладка для служебных операций.
    def __init__(self, parent, db):
        super().__init__(parent)
        self.db = db
        self.indicator_service = IndicatorService(db)
        self.period_repo = PeriodRepository(db)

        # --- Верхняя часть: два блока рядом ---
        frame_top = tk.Frame(self)
        frame_top.pack(fill="x", padx=10, pady=5)

        # Левый блок: Отладка индикаторов
        self.frame_debug = tk.LabelFrame(frame_top, text="Отладка индикаторов", padx=5, pady=5)
        self.frame_debug.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self._build_debug_section(self.frame_debug)

        # Правый блок: Проверить и скорректировать периоды
        self.frame_ops = tk.LabelFrame(
            frame_top, text="Проверить и скорректировать периоды", padx=5, pady=5
        )
        self.frame_ops.pack(side="left", fill="both", expand=True, padx=(5, 0))
        self._build_ops_section(self.frame_ops)

        # --- Нижняя часть: общий лог ---
        tk.Label(self, text="Лог операций:", font=("Arial", 9, "bold")).pack(anchor="w", padx=10)
        self.log_text = tk.Text(self, height=15, state="disabled", bg="#f0f0f0")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def _build_debug_section(self, parent):
        self.btn_today = tk.Button(
            parent,
            text="Пересчитать индикаторы за сегодня",
            command=lambda: self.calculate_indicators("today"),
            fg="green",
            font=("Arial", 10, "bold")
        )
        self.btn_today.pack(pady=3, fill="x")

        self.btn_yesterday = tk.Button(
            parent,
            text="Пересчитать индикаторы за вчера",
            command=lambda: self.calculate_indicators("yesterday"),
            font=("Arial", 10)
        )
        self.btn_yesterday.pack(pady=3, fill="x")

        frame_custom = tk.Frame(parent)
        frame_custom.pack(pady=3, fill="x")

        tk.Label(frame_custom, text="Дата:").pack(side="left", padx=(0, 5))

        now = datetime_utils.to_datetime(datetime_utils.get_now_iso())
        self.date_entry = DateEntry(
            frame_custom, width=12,
            background='darkblue', foreground='white', borderwidth=2,
            year=now.year, month=now.month, day=now.day,
            date_pattern='yyyy-mm-dd', locale='ru_RU'
        )
        self.date_entry.pack(side="left", padx=5)

        self.btn_custom = tk.Button(
            frame_custom,
            text="Пересчитать за выбранную дату",
            command=lambda: self.calculate_indicators("custom"),
            font=("Arial", 10)
        )
        self.btn_custom.pack(side="left", padx=5)

    def _build_ops_section(self, parent):
        tk.Label(
            parent,
            text=(
                "Пересчитывает fact_start/fact_end для всех day-периодов "
                "и обновляет границы week/month. Все изменения пишутся в лог."
            ),
            justify="left", anchor="w", wraplength=320, fg="#555"
        ).pack(anchor="w", pady=3)

        self.btn_check_periods = tk.Button(
            parent,
            text="Проверить и скорректировать периоды",
            command=self.check_and_fix_periods,
            font=("Arial", 10, "bold"),
            fg="darkblue"
        )
        self.btn_check_periods.pack(pady=10, fill="x")

    def _log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def calculate_indicators(self, mode="today"):
        try:
            if mode == "today":
                target_date = datetime_utils.get_today_str()
                label = "сегодня"
            elif mode == "yesterday":
                today_dt = datetime_utils.to_datetime(datetime_utils.get_now_iso())
                target_date = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")
                label = "вчера"
            elif mode == "custom":
                target_date = self.date_entry.get_date().strftime("%Y-%m-%d")
                label = f"дату {target_date}"
            else:
                target_date = datetime_utils.get_today_str()
                label = "сегодня"

            self._log("")
            self._log("-----" + datetime_utils.get_now_iso() + "-----")
            self._log(f"Запуск пересчета за {label} ({target_date})...")

            messages = self.indicator_service.recalculate_for_date(target_date)

            self._log("УСПЕХ: Индикаторы пересчитаны.")
            if messages:
                for msg in messages:
                    self._log(f"  {msg}")
            self._log("Проверьте таблицу indicator_values в базе.")

        except Exception as e:
            self._log(f"ОШИБКА: {e}")

    def check_and_fix_periods(self):
        """Пересчитывает fact_start/fact_end для всех day-периодов и week/month.
        Логирует все изменения и итоговую сводку."""
        self._log("")
        self._log("-----" + datetime_utils.get_now_iso() + "-----")
        self._log("Проверка и корректировка периодов...")
        try:
            day_changes = self.period_repo.refresh_all_day_bounds()
            for c in day_changes:
                self._log(
                    f"  [day {c['period_value']}] "
                    f"fact_start: {c['old_fact_start']} → {c['new_fact_start']}; "
                    f"fact_end: {c['old_fact_end']} → {c['new_fact_end']}"
                )

            parent_changes = self.period_repo.refresh_all_aggregate_bounds()
            for c in parent_changes:
                self._log(
                    f"  [{c['period_type']} {c['period_value']}] "
                    f"fact_start: {c['old_fact_start']} → {c['new_fact_start']}; "
                    f"fact_end: {c['old_fact_end']} → {c['new_fact_end']}"
                )

            self._log("")
            if not day_changes and not parent_changes:
                self._log("Итог: изменений нет.")
            else:
                self._log(
                    f"Итог: изменено day-периодов: {len(day_changes)}, "
                    f"week/month: {len(parent_changes)}."
                )
        except Exception as e:
            self._log(f"ОШИБКА: {e}")