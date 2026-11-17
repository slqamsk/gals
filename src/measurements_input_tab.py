# src/measurements_input_tab.py
# Вкладка «Ввод измерения»: выбор типа → динамическая форма по компонентам.

import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry

from . import datetime_utils


class MeasurementsInputTab(tk.Frame):
    def __init__(self, parent, repo, prefs_repo):
        super().__init__(parent)
        self.repo = repo
        self.prefs_repo = prefs_repo
        self.current_type_id = None
        self.component_entries = {}
        self.types_map = {}

        self._build_ui()
        self._load_types()

    def _build_ui(self):
        frame_top = tk.Frame(self)
        frame_top.pack(fill="x", padx=15, pady=(15, 5))

        tk.Label(frame_top, text="Тип измерения:",
                 font=("Arial", 10, "bold")).pack(side="left")
        self.cb_type = ttk.Combobox(frame_top, state="readonly", width=40)
        self.cb_type.pack(side="left", padx=10)
        self.cb_type.bind("<<ComboboxSelected>>", self._on_type_changed)

        self.frame_form = tk.Frame(self)
        self.frame_form.pack(fill="both", expand=True, padx=15, pady=10)

        self.lbl_hint = tk.Label(
            self.frame_form,
            text="Выберите тип измерения, чтобы начать ввод",
            fg="gray", font=("Arial", 10, "italic")
        )
        self.lbl_hint.pack(pady=20)

    def _load_types(self):
        types = self.repo.get_all_types()
        self.types_map = {t[1]: t[0] for t in types}
        self.cb_type['values'] = list(self.types_map.keys())

        last_id = self.prefs_repo.get("measurements_last_type_id")
        if last_id is not None:
            for name, tid in self.types_map.items():
                if tid == last_id:
                    self.cb_type.set(name)
                    self._on_type_changed()
                    return

    def refresh_all(self):
        prev = self.current_type_id
        self._load_types()
        if prev is not None and prev in self.types_map.values():
            for name, tid in self.types_map.items():
                if tid == prev:
                    self.cb_type.set(name)
                    self._on_type_changed()
                    return

    def save_state(self):
        if self.current_type_id is not None:
            self.prefs_repo.set("measurements_last_type_id", self.current_type_id)

    def _on_type_changed(self, event=None):
        type_name = self.cb_type.get()
        type_id = self.types_map.get(type_name)
        if type_id is None:
            return
        self.current_type_id = type_id
        self.prefs_repo.set("measurements_last_type_id", type_id)
        self._build_form(type_id)

    def _build_form(self, type_id):
        for w in self.frame_form.winfo_children():
            w.destroy()
        self.component_entries = {}

        components = self.repo.get_components_full_for_type(type_id)
        if not components:
            tk.Label(
                self.frame_form,
                text=(
                    "У этого типа измерения нет компонентов.\n"
                    "Создайте их в разделе «Настройки» → «Типы и компоненты»."
                ),
                fg="red", font=("Arial", 10)
            ).pack(pady=20)
            return

        # Дата и время
        frame_dt = tk.Frame(self.frame_form)
        frame_dt.pack(fill="x", pady=(0, 10))

        tk.Label(frame_dt, text="Дата и время:",
                 font=("Arial", 10, "bold"), width=20, anchor="w").pack(side="left")

        now = datetime_utils.to_datetime(datetime_utils.get_now_iso())
        self.cal = DateEntry(
            frame_dt, width=12, background='darkblue', foreground='white', borderwidth=2,
            year=now.year, month=now.month, day=now.day,
            date_pattern='yyyy-mm-dd', locale='ru_RU'
        )
        self.cal.pack(side="left", padx=5)

        self.var_hour = tk.StringVar(value=now.strftime("%H"))
        self.var_min = tk.StringVar(value=now.strftime("%M"))
        tk.Spinbox(frame_dt, from_=0, to=23, width=3, textvariable=self.var_hour,
                   format="%02.0f", font=("Arial", 11)).pack(side="left", padx=(10, 2))
        tk.Label(frame_dt, text=":", font=("Arial", 11, "bold")).pack(side="left")
        tk.Spinbox(frame_dt, from_=0, to=59, width=3, textvariable=self.var_min,
                   format="%02.0f", font=("Arial", 11)).pack(side="left", padx=2)

        tk.Button(frame_dt, text="Сейчас", command=self._set_now,
                  font=("Arial", 8)).pack(side="left", padx=10)

        # Компоненты
        tk.Label(self.frame_form, text="Значения:", font=("Arial", 10, "bold"),
                 anchor="w").pack(fill="x", pady=(10, 5))

        frame_values = tk.Frame(self.frame_form)
        frame_values.pack(fill="x")

        for comp in components:
            row = tk.Frame(frame_values)
            row.pack(fill="x", pady=3)

            label_text = comp["name"]
            if comp["is_required"]:
                label_text += " *"
            tk.Label(row, text=label_text, width=25, anchor="w",
                     font=("Arial", 10)).pack(side="left")

            entry = tk.Entry(row, width=20, font=("Arial", 10))
            entry.pack(side="left")

            tk.Label(row, text=comp["unit_display"], fg="#555",
                     font=("Arial", 10), width=15, anchor="w").pack(side="left", padx=5)

            self.component_entries[comp["id"]] = {
                "entry": entry,
                "required": comp["is_required"],
                "name": comp["name"],
            }

        tk.Label(self.frame_form, text="* — обязательное поле",
                 fg="gray", font=("Arial", 8, "italic")).pack(anchor="w", pady=(5, 10))

        # Заметки
        frame_notes = tk.Frame(self.frame_form)
        frame_notes.pack(fill="x", pady=(10, 5))
        tk.Label(frame_notes, text="Заметки:", width=20, anchor="w",
                 font=("Arial", 10, "bold")).pack(side="left")
        self.ent_notes = tk.Entry(frame_notes, font=("Arial", 10))
        self.ent_notes.pack(side="left", fill="x", expand=True, padx=5)

        # Кнопки
        frame_btns = tk.Frame(self.frame_form)
        frame_btns.pack(fill="x", pady=15)

        tk.Button(frame_btns, text="Сохранить", command=self._on_save,
                  font=("Arial", 10, "bold"), fg="green", width=15).pack(side="left")
        tk.Button(frame_btns, text="Очистить", command=self._on_clear,
                  font=("Arial", 10), width=15).pack(side="left", padx=10)

    def _set_now(self):
        now = datetime_utils.to_datetime(datetime_utils.get_now_iso())
        self.cal.set_date(now)
        self.var_hour.set(now.strftime("%H"))
        self.var_min.set(now.strftime("%M"))

    def _on_clear(self):
        for info in self.component_entries.values():
            info["entry"].delete(0, tk.END)
        if hasattr(self, 'ent_notes'):
            self.ent_notes.delete(0, tk.END)

    def _on_save(self):
        if not self.current_type_id:
            messagebox.showwarning("Ошибка", "Выберите тип измерения")
            return

        try:
            h = int(self.var_hour.get())
            m = int(self.var_min.get())
        except (ValueError, TypeError):
            messagebox.showerror("Ошибка", "Некорректное время")
            return
        if not (0 <= h <= 23 and 0 <= m <= 59):
            messagebox.showerror("Ошибка", "Часы 0-23, минуты 0-59")
            return

        sd = self.cal.get_date()
        measured_at = f"{sd.year}-{sd.month:02d}-{sd.day:02d}T{h:02d}:{m:02d}:00+03:00"

        values = {}
        for comp_id, info in self.component_entries.items():
            raw = info["entry"].get().strip()
            if not raw:
                if info["required"]:
                    messagebox.showerror(
                        "Ошибка",
                        f"Не заполнено обязательное поле: {info['name']}"
                    )
                    return
                continue
            try:
                values[comp_id] = float(raw.replace(",", "."))
            except ValueError:
                messagebox.showerror(
                    "Ошибка",
                    f"Некорректное число в поле «{info['name']}»: {raw}"
                )
                return

        try:
            self.repo.add_session(
                measurement_type_id=self.current_type_id,
                measured_at=measured_at,
                notes=self.ent_notes.get().strip() or None,
                values=values,
            )
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось сохранить измерение:\n{e}")
            return

        messagebox.showinfo("Успех", "Измерение сохранено.")
        self._on_clear()