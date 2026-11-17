# src/tools_web_events_tab.py
# Подвкладка "Web-события" (внутри Инструментов).
# Настройки подключения, синхронизация, создание активности «Ночной сон».

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from tkcalendar import DateEntry

from . import datetime_utils
from .web_sync import sync as web_sync
from .web_events_service import add_sleep_from_web_events
from .web_time_events_repo import WebTimeEventsRepository


def _require_int_pref(prefs_repo, key: str) -> int:
    """Возвращает значение preference как int.
    Если ключ отсутствует (None) — бросает ValueError."""
    val = prefs_repo.get(key)
    if val is None:
        raise ValueError(
            f"Настройка '{key}' отсутствует в preferences. "
            f"Проверьте src/defaults.py и перезапустите приложение."
        )
    try:
        return int(val)
    except (TypeError, ValueError):
        raise ValueError(
            f"Настройка '{key}' имеет некорректное значение: {val!r} (ожидалось целое число)."
        )


class ToolsWebEventsTab(tk.Frame):
    def __init__(self, parent, db, prefs_repo):
        super().__init__(parent)
        self.db = db
        self.prefs_repo = prefs_repo

        # --- Секция настроек подключения ---
        frame_settings = tk.LabelFrame(self, text="Настройки подключения", padx=5, pady=5)
        frame_settings.pack(fill="x", padx=10, pady=5)

        row1 = tk.Frame(frame_settings)
        row1.pack(fill="x", pady=2)
        tk.Label(row1, text="URL API:", width=12, anchor="w").pack(side="left")
        self.ent_url = tk.Entry(row1, width=50)
        self.ent_url.pack(side="left", fill="x", expand=True, padx=5)

        row2 = tk.Frame(frame_settings)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="API-ключ:", width=12, anchor="w").pack(side="left")
        self.ent_key = tk.Entry(row2, width=50, show="*")
        self.ent_key.pack(side="left", fill="x", expand=True, padx=5)

        row3 = tk.Frame(frame_settings)
        row3.pack(fill="x", pady=5)
        self.btn_save_settings = tk.Button(
            row3, text="Сохранить настройки",
            command=self.on_save_settings, font=("Arial", 10, "bold")
        )
        self.btn_save_settings.pack(side="left")

        self.lbl_settings_state = tk.Label(row3, text="", anchor="w", fg="#555")
        self.lbl_settings_state.pack(side="left", padx=15)

        # Заполняем поля текущими значениями
        self.ent_url.insert(0, self.prefs_repo.get("web_sync_url") or "")
        self.ent_key.insert(0, self.prefs_repo.get("web_sync_key") or "")

        # --- Секция синхронизации ---
        frame_sync = tk.LabelFrame(self, text="Синхронизация", padx=5, pady=5)
        frame_sync.pack(fill="x", padx=10, pady=5)

        self.btn_sync = tk.Button(
            frame_sync, text="Синхронизировать с сервером",
            command=self.on_sync, font=("Arial", 10, "bold"), fg="darkblue"
        )
        self.btn_sync.pack(pady=5)

        # Кнопка "Пометить все как обработанные" — работает с событиями в БД,
        # поэтому в этой же секции (обе кнопки — операции с событиями).
        self.btn_mark_all = tk.Button(
            frame_sync, text="Пометить все как обработанные",
            command=self.on_mark_all_processed, font=("Arial", 10), fg="#555"
        )
        self.btn_mark_all.pack(pady=(0, 5))

        self.lbl_sync_state = tk.Label(frame_sync, text="", anchor="w", fg="#555")
        self.lbl_sync_state.pack(fill="x")

        # --- Секция создания сна ---
        frame_sleep = tk.LabelFrame(self, text="Добавить сон из web-событий",
                                    padx=5, pady=5)
        frame_sleep.pack(fill="x", padx=10, pady=5)

        frame_date = tk.Frame(frame_sleep)
        frame_date.pack(fill="x", pady=5)

        tk.Label(frame_date, text="Дата сна:").pack(side="left", padx=(0, 5))

        now = datetime_utils.to_datetime(datetime_utils.get_now_iso())
        self.date_entry = DateEntry(
            frame_date, width=12,
            background='darkblue', foreground='white', borderwidth=2,
            year=now.year, month=now.month, day=now.day,
            date_pattern='yyyy-mm-dd', locale='ru_RU'
        )
        self.date_entry.pack(side="left", padx=5)

        self.lbl_window = tk.Label(frame_sleep, text="", anchor="w", fg="#777")
        self.lbl_window.pack(fill="x")

        self.btn_add_sleep = tk.Button(
            frame_sleep, text="Добавить сон",
            command=self.on_add_sleep, font=("Arial", 10, "bold"), fg="green"
        )
        self.btn_add_sleep.pack(pady=5)

        # --- Лог ---
        tk.Label(self, text="Лог операций:", font=("Arial", 9, "bold")).pack(
            anchor="w", padx=10
        )
        self.log_text = tk.Text(self, height=10, state="disabled", bg="#f0f0f0")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

        self._update_info()
        self.date_entry.bind("<<DateEntrySelected>>", lambda e: self._update_info())

    def _log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def on_save_settings(self):
        url = self.ent_url.get().strip()
        key = self.ent_key.get().strip()

        if not url:
            messagebox.showwarning("Ошибка", "URL API не может быть пустым.")
            return
        if not key:
            messagebox.showwarning("Ошибка", "API-ключ не может быть пустым.")
            return

        self.prefs_repo.set("web_sync_url", url)
        self.prefs_repo.set("web_sync_key", key)

        self.lbl_settings_state.config(text="✓ Сохранено", fg="green")
        self.after(2000, lambda: self.lbl_settings_state.config(text=""))
        self._update_info()

    def _update_info(self):
        key = self.prefs_repo.get("web_sync_key") or ""
        if key:
            self.lbl_sync_state.config(
                text="API-ключ задан. Синхронизация доступна.", fg="#555"
            )
        else:
            self.lbl_sync_state.config(
                text="API-ключ не задан. Заполните поле выше и нажмите «Сохранить».",
                fg="red"
            )

        # Окно для выбранной даты + количество необработанных событий в окне.
        try:
            target_date = self.date_entry.get_date().strftime("%Y-%m-%d")
            H = _require_int_pref(self.prefs_repo, "web_events_sleep_window_start_hour")
            dt_D = datetime.strptime(target_date, "%Y-%m-%d")
            start_naive = (dt_D - timedelta(days=1)).replace(hour=H, minute=0, second=0)
            end_naive = dt_D.replace(hour=H, minute=0, second=0)

            start_iso = start_naive.replace(tzinfo=datetime_utils._USER_TZ).isoformat()
            end_iso = end_naive.replace(tzinfo=datetime_utils._USER_TZ).isoformat()

            try:
                events_repo = WebTimeEventsRepository(self.db)
                in_window = events_repo.get_unprocessed_in_range(start_iso, end_iso)
                count_in_window = len(in_window)
                count_total = events_repo.get_unprocessed_count()
            except Exception:
                count_in_window = 0
                count_total = 0

            color = "#333" if count_in_window > 0 else "#c00"

            self.lbl_window.config(
                text=(
                    f"Окно: {start_naive.strftime('%d.%m.%Y %H:%M')} – "
                    f"{end_naive.strftime('%d.%m.%Y %H:%M')} (UTC+3). "
                    f"Необработанных событий в окне: {count_in_window} "
                    f"(всего необработанных: {count_total})."
                ),
                fg=color,
            )
        except ValueError as e:
            self.lbl_window.config(text=f"Ошибка настроек: {e}", fg="red")
        except Exception:
            pass

    def on_sync(self):
        self._log("")
        self._log("-----" + datetime_utils.get_now_iso() + "-----")
        self._log("Синхронизация с сервером...")
        try:
            result = web_sync(self.prefs_repo)
            self._log(
                f"Получено с сервера: {result['fetched']}, "
                f"добавлено в БД: {result['inserted']}, "
                f"пропущено (уже были): {result['skipped']}, "
                f"удалено на сервере: {result['deleted']}"
            )
            for err in result["errors"]:
                self._log(f"ОШИБКА: {err}")
            if result["ok"]:
                self._log("Синхронизация завершена успешно.")
            else:
                self._log("Синхронизация завершена с ошибками.")
        except Exception as e:
            self._log(f"ОШИБКА: {e}")
        self._update_info()

    def on_mark_all_processed(self):
        self._log("")
        self._log("-----" + datetime_utils.get_now_iso() + "-----")

        try:
            events_repo = WebTimeEventsRepository(self.db)
            count = events_repo.get_unprocessed_count()
        except Exception as e:
            self._log(f"ОШИБКА: {e}")
            return

        if count == 0:
            self._log("Необработанных событий нет — помечать нечего.")
            self._update_info()
            return

        if not messagebox.askyesno(
            "Подтверждение",
            f"Пометить как обработанные все необработанные события?\n\n"
            f"Всего: {count}.\n"
            f"Данные не удаляются, меняется только флаг processed (0 → 1)."
        ):
            self._log("Отменено пользователем.")
            return

        self._log(f"Пометка {count} необработанных событий как обработанных...")
        try:
            marked = events_repo.mark_all_unprocessed()
        except Exception as e:
            self._log(f"ОШИБКА: {e}")
            self._update_info()
            return

        self._log(f"УСПЕХ: помечено событий: {len(marked)}.")
        self._log("Помеченные записи:")
        for row in marked:
            _id, server_id, etype, etime = row
            self._log(
                f"  - id={_id}, server_event_id={server_id}, "
                f"{etype}: {etime}"
            )
        self._update_info()

    def on_add_sleep(self):
        self._log("")
        self._log("-----" + datetime_utils.get_now_iso() + "-----")
        try:
            target_date = self.date_entry.get_date().strftime("%Y-%m-%d")
        except Exception as e:
            self._log(f"ОШИБКА даты: {e}")
            return

        # Предупреждение, если дата не сегодняшняя (частая ошибка — забыли сменить дату)
        today_str = datetime_utils.get_today_str()
        if target_date != today_str:
            try:
                today_dt = datetime.strptime(today_str, "%Y-%m-%d")
                target_dt = datetime.strptime(target_date, "%Y-%m-%d")
                today_disp = today_dt.strftime("%d.%m.%Y")
                target_disp = target_dt.strftime("%d.%m.%Y")
            except ValueError:
                today_disp = today_str
                target_disp = target_date
            self._log(
                f"ВНИМАНИЕ: СЕГОДНЯ {today_disp}, "
                f"А ВЫ ЗАПУСКАЕТЕ СОЗДАНИЕ СНА ЗА {target_disp}!!!"
            )

        self._log(f"Создание сна за {target_date}...")
        try:
            result = add_sleep_from_web_events(self.prefs_repo, target_date)
            if result["ok"]:
                self._log(
                    f"УСПЕХ: создана активность «Ночной сон», "
                    f"{result['start']} – {result['end']}, "
                    f"длительность {result['duration']} мин. "
                    f"Помечено событий: {result['processed']}."
                )
            else:
                self._log("НЕ УДАЛОСЬ:")
                for err in result["errors"]:
                    self._log(f"  {err}")
        except Exception as e:
            self._log(f"ОШИБКА: {e}")
        self._update_info()