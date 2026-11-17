# src/manual_activities_tab.py
# Вкладка для ручного управления активностями.
#
# Кнопка «Добавить» открывает диалог с полями:
#   - слева дерево ролей/подролей (фильтр),
#   - справа: тип активности (отфильтрован по роли/подроли),
#     обязанность, роль, подроль (фиксируются из фильтра), дата,
#     время начала + «Установить текущее», время окончания, заметки.
#
# Геометрия окна и позиция разделителя сохраняются в preferences
# (manual_activity_dialog_geometry, manual_activity_dialog_sash).

import json
import tkinter as tk
from tkinter import messagebox, ttk
from tksheet import Sheet
from tkcalendar import DateEntry
from datetime import datetime
from . import datetime_utils
from .activities_repo import ActivitiesRepository
from .activity_types_repo import ActivityTypesRepository
from .roles_repo import RolesRepository
from .sub_roles_repo import SubRolesRepository
from .regular_duties_repo import RegularDutiesRepository


class ManualActivitiesTab(tk.Frame):
    def __init__(self, parent, activities_repo: ActivitiesRepository, types_repo: ActivityTypesRepository,
                 roles_repo: RolesRepository, sub_roles_repo: SubRolesRepository, prefs_repo):
        super().__init__(parent)
        self.activities_repo = activities_repo
        self.types_repo = types_repo
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.prefs_repo = prefs_repo
        self.duties_repo = RegularDutiesRepository(self.activities_repo.db)

        self.sort_col = self.prefs_repo.get("manual_activities_sort_col")
        if self.sort_col is None:
            self.sort_col = 5
        self.sort_asc = self.prefs_repo.get("manual_activities_sort_asc")
        if self.sort_asc is None:
            self.sort_asc = False

        self.types_map = {}
        self.types_data = {}
        self.roles_map = {}
        self.sub_roles_map = {}
        self.roles_id_to_name = {}
        self.sub_roles_id_to_name = {}
        self.duties_map = {}
        self.duties_data = {}

        self.raw_iso_data = {}

        frame_buttons = tk.Frame(self)
        frame_buttons.pack(pady=5, padx=10, fill="x")

        self.btn_add = tk.Button(frame_buttons, text="Добавить", command=self.on_add_row)
        self.btn_add.pack(side="left", padx=5)

        self.btn_del = tk.Button(frame_buttons, text="Удалить выбранное", command=self.on_delete_row)
        self.btn_del.pack(side="left", padx=5)

        self.btn_refresh = tk.Button(frame_buttons, text="Обновить", command=self.refresh_table)
        self.btn_refresh.pack(side="left", padx=5)

        lbl_hint = tk.Label(
            frame_buttons,
            text="(Двойной клик по 'Тип', 'Обязанность', 'Роль', 'Начало' или 'Конец' откроет выбор)",
            fg="gray"
        )
        lbl_hint.pack(side="right", padx=5)

        frame_filter = tk.Frame(self)
        frame_filter.pack(pady=0, padx=10, fill="x")

        tk.Label(frame_filter, text="Фильтр:").pack(side="left", padx=(0, 5))

        self.cb_filter = ttk.Combobox(frame_filter, values=["Все", "За день"], state="readonly", width=10)
        self.cb_filter.pack(side="left", padx=5)
        self.cb_filter.bind("<<ComboboxSelected>>", self._on_filter_changed)

        self.date_entry = DateEntry(
            frame_filter, width=12, background='darkblue', foreground='white', borderwidth=2,
            date_pattern='yyyy-mm-dd', locale='ru_RU'
        )
        self.date_entry.pack(side="left", padx=5)
        self.date_entry.bind("<<DateEntrySelected>>", self._on_filter_changed)

        self.sheet = Sheet(
            self,
            headers=["ID", "Тип", "Обязанность", "Роль", "Под-роль", "Начало", "Конец",
                     "Длит. (мин)", "Чистая (мин)", "Перерывы (мин)", "Вовлеч. (%)",
                     "Оценка (0/1)", "Источник", "Заметки", "Создано", "Обновлено"],
            show_row_index=False,
            show_top_left=False,
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            table_grid_fg="#000000",
            outline_thickness=1,
            header_bg="#f0f0f0",
            header_fg="#000000",
            font=("Arial", 10, "normal"),
            header_font=("Arial", 10, "bold"),
            row_height=25,
            table_wrap="w",
            auto_resize_row_heights=True,
        )
        self.sheet.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        self.sheet.enable_bindings("all")
        self.sheet.readonly_columns(columns=[0, 1, 2, 3, 4, 5, 6, 14, 15])

        self.sheet.MT.bind("<Double-Button-1>", self.on_double_click, add="+")
        self.sheet.CH.bind("<Double-Button-1>", self.on_header_double_click, add="+")

        self.sheet.extra_bindings("end_edit_cell", self.on_cell_edited)

        self._load_state()
        self.refresh_table()

    def _load_state(self):
        try:
            widths = json.loads(self.prefs_repo.get("manual_activities_col_widths"))
            if isinstance(widths, list) and len(widths) == 16 and all(w is not None for w in widths):
                self.sheet.set_column_widths([int(w) for w in widths])
            else:
                raise ValueError()
        except Exception:
            self.sheet.set_column_widths(
                [50, 100, 150, 100, 100, 120, 120, 80, 80, 80, 80, 80, 100, 150, 120, 120]
            )

        mode = self.prefs_repo.get("manual_activities_filter_mode") or "all"
        fdate = self.prefs_repo.get("manual_activities_filter_date")

        if not fdate:
            fdate = datetime_utils.get_today_str()

        self.cb_filter.set("За день" if mode == "day" else "Все")

        try:
            dt = datetime.strptime(fdate, "%Y-%m-%d")
            self.date_entry.set_date(dt)
        except Exception:
            pass

        if mode == "all":
            self.date_entry.config(state="disabled")
        else:
            self.date_entry.config(state="normal")

    def save_state(self):
        widths = self.sheet.get_column_widths()
        self.prefs_repo.set("manual_activities_col_widths", json.dumps(widths))
        self.prefs_repo.set("manual_activities_sort_col", self.sort_col)
        self.prefs_repo.set("manual_activities_sort_asc", self.sort_asc)

        if self.cb_filter.get() == "За день":
            self.prefs_repo.set("manual_activities_filter_mode", "day")
            self.prefs_repo.set("manual_activities_filter_date", self.date_entry.get_date().strftime("%Y-%m-%d"))
        else:
            self.prefs_repo.set("manual_activities_filter_mode", "all")

    def _on_filter_changed(self, event=None):
        mode = self.cb_filter.get()
        if mode == "За день":
            self.date_entry.config(state="normal")
        else:
            self.date_entry.config(state="disabled")
        self.refresh_table()

    def on_header_double_click(self, event):
        col = self.sheet.identify_column(event)
        if col == "" or col is None:
            return

        try:
            col = int(col)
        except ValueError:
            return

        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True

        self.save_state()
        self.refresh_table()
        return "break"

    def _update_headers(self):
        base_headers = ["ID", "Тип", "Обязанность", "Роль", "Под-роль", "Начало", "Конец",
                        "Длит. (мин)", "Чистая (мин)", "Перерывы (мин)", "Вовлеч. (%)",
                        "Оценка (0/1)", "Источник", "Заметки", "Создано", "Обновлено"]

        if self.sort_col is not None and 0 <= self.sort_col < len(base_headers):
            arrow = " ▲" if self.sort_asc else " ▼"
            base_headers[self.sort_col] += arrow

        self.sheet.headers(base_headers)

    def refresh_table(self):
        self.types_map = {t[1]: t[0] for t in self.types_repo.get_all()}
        self.types_data = {t[0]: t for t in self.types_repo.get_all()}

        self.roles_map = {r[1]: r[0] for r in self.roles_repo.get_all()}
        self.roles_id_to_name = {r[0]: r[1] for r in self.roles_repo.get_all()}

        self.sub_roles_map = {}
        self.sub_roles_id_to_name = {}
        for r in self.roles_repo.get_all():
            for sr in self.sub_roles_repo.get_by_parent(r[0]):
                self.sub_roles_map[sr[1]] = sr[0]
                self.sub_roles_id_to_name[sr[0]] = sr[1]

        self.duties_map = {}
        self.duties_data = {}
        for d in self.duties_repo.get_all():
            d_id, d_name, _d_desc, _d_ord, _d_imp, d_type_id, d_period, d_role_id, d_sub_id, _c, _u = d
            self.duties_map[d_name] = d_id
            self.duties_data[d_name] = {
                "id": d_id,
                "execution_order": _d_ord,
                "importance": _d_imp,
                "activity_type_id": d_type_id,
                "period_type": d_period,
                "role_id": d_role_id,
                "sub_role_id": d_sub_id,
            }

        target_date = None
        if self.cb_filter.get() == "За день":
            target_date = self.date_entry.get_date().strftime("%Y-%m-%d")

        data = self.activities_repo.get_all(target_date=target_date)

        self.raw_iso_data = {}
        formatted_data = []

        for row in data:
            row_list = list(row)
            act_id = str(row_list[0])

            start_iso = row_list[5]
            end_iso = row_list[6]
            self.raw_iso_data[act_id] = {
                "start": start_iso or "",
                "end": end_iso or "",
                "created": row_list[14] or "",
                "updated": row_list[15] or "",
            }

            if start_iso:
                row_list[5] = datetime_utils.to_display(start_iso)
            if end_iso:
                row_list[6] = datetime_utils.to_display(end_iso)

            if row_list[14]:
                row_list[14] = datetime_utils.to_display(row_list[14])
            if row_list[15]:
                row_list[15] = datetime_utils.to_display(row_list[15])

            formatted_data.append([val if val is not None else "" for val in row_list])

        if self.sort_col is not None:
            def get_sort_key(row):
                col = self.sort_col
                if col in [5, 6, 14, 15]:
                    act_id = str(row[0])
                    raw = self.raw_iso_data.get(act_id, {})
                    if col == 5: return raw.get("start", "")
                    elif col == 6: return raw.get("end", "")
                    elif col == 14: return raw.get("created", "")
                    else: return raw.get("updated", "")
                elif col in [0, 7, 8, 9, 10, 11]:
                    try:
                        return int(row[col])
                    except (ValueError, TypeError):
                        return 0
                else:
                    return str(row[col]).lower()

            formatted_data.sort(key=get_sort_key, reverse=not self.sort_asc)

        self.sheet.set_sheet_data(formatted_data, reset_col_positions=False)
        self._update_headers()

    def on_double_click(self, event):
        row = self.sheet.identify_row(event)
        col = self.sheet.identify_column(event)

        if row == "" or col == "":
            return

        try:
            row = int(row)
            col = int(col)
        except ValueError:
            return

        if col == 1:
            self._open_type_picker(row)
        elif col == 2:
            self._open_duty_picker(row)
        elif col == 3 or col == 4:
            self._open_role_picker(row)
        elif col == 5 or col == 6:
            self._open_datetime_picker(row, col)

    def _open_datetime_picker(self, row, col):
        picker = tk.Toplevel(self)
        picker.transient(self.winfo_toplevel())
        picker.title("Выбор даты и времени")

        win_w, win_h = 300, 400
        picker.update_idletasks()
        screen_width = picker.winfo_screenwidth()
        screen_height = picker.winfo_screenheight()
        pos_x = (screen_width - win_w) // 2
        pos_y = (screen_height - win_h) // 2
        picker.geometry(f"{win_w}x{win_h}+{pos_x}+{pos_y}")
        picker.grab_set()

        act_id = str(self.sheet.get_cell_data(row, 0))
        key = "start" if col == 5 else "end"

        current_iso = self.raw_iso_data.get(act_id, {}).get(key, "")

        now = datetime.now()
        init_year, init_month, init_day = now.year, now.month, now.day
        init_hour, init_minute = now.hour, now.minute

        if current_iso:
            try:
                dt = datetime_utils.to_datetime(current_iso)
                init_year, init_month, init_day = dt.year, dt.month, dt.day
                init_hour, init_minute = dt.hour, dt.minute
            except Exception:
                pass

        tk.Label(picker, text="Дата:", font=("Arial", 10, "bold")).pack(pady=(15, 0))
        cal = DateEntry(picker, width=12, background='darkblue',
                        foreground='white', borderwidth=2,
                        year=init_year, month=init_month, day=init_day,
                        locale='ru_RU')
        cal.pack(pady=5)

        tk.Label(picker, text="Время (Часы : Минуты):", font=("Arial", 10, "bold")).pack(pady=(15, 5))

        time_frame = tk.Frame(picker)
        time_frame.pack(pady=5)

        var_hour = tk.StringVar(value=f"{init_hour:02d}")
        var_minute = tk.StringVar(value=f"{init_minute:02d}")

        spin_hour = tk.Spinbox(time_frame, from_=0, to=23, width=3, textvariable=var_hour, format="%02.0f",
                               font=("Arial", 11))
        spin_hour.pack(side="left", padx=2)

        tk.Label(time_frame, text=":", font=("Arial", 11, "bold")).pack(side="left")

        spin_minute = tk.Spinbox(time_frame, from_=0, to=59, width=3, textvariable=var_minute, format="%02.0f",
                                 font=("Arial", 11))
        spin_minute.pack(side="left", padx=2)

        def save_datetime():
            try:
                hours = int(var_hour.get())
                minutes = int(var_minute.get())
            except ValueError:
                messagebox.showerror("Ошибка", "Введите корректное число часов и минут!", parent=picker)
                return

            if not (0 <= hours <= 23) or not (0 <= minutes <= 59):
                messagebox.showerror("Ошибка", "Часы от 0 до 23, минуты от 0 до 59!", parent=picker)
                return

            selected_date = cal.get_date()
            dt_iso_str = (
                f"{selected_date.year}-{selected_date.month:02d}-{selected_date.day:02d}"
                f"T{hours:02d}:{minutes:02d}:00+03:00"
            )

            self.raw_iso_data.setdefault(act_id, {})[key] = dt_iso_str
            self.sheet.set_cell_data(row, col, datetime_utils.to_display(dt_iso_str))

            self._save_row(row)
            picker.destroy()

        tk.Button(picker, text="Применить", command=save_datetime, width=15, height=2,
                  font=("Arial", 10, "bold")).pack(pady=25)

    def _open_type_picker(self, row):
        picker = tk.Toplevel(self)
        picker.transient(self.winfo_toplevel())
        picker.title("Выбор типа активности")

        picker.update_idletasks()
        screen_width = picker.winfo_screenwidth()
        screen_height = picker.winfo_screenheight()
        pos_x = (screen_width - 300) // 2
        pos_y = (screen_height - 400) // 2
        picker.geometry(f"300x400+{pos_x}+{pos_y}")
        picker.grab_set()

        tree = ttk.Treeview(picker, columns=("id",), show="tree", selectmode="browse")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        types = self.types_repo.get_all()
        for t in types:
            tree.insert("", "end", text=t[1], values=(t[0],))

        def select(event=None):
            sel = tree.selection()
            if not sel:
                return
            item = tree.item(sel[0])
            type_id = item["values"][0]
            type_name = item["text"]

            current_duty_name = self.sheet.get_cell_data(row, 2) or ""
            if current_duty_name:
                d_info = self.duties_data.get(current_duty_name)
                if d_info and d_info["activity_type_id"] != type_id:
                    if not messagebox.askyesno(
                        "Смена типа",
                        f"Обязанность «{current_duty_name}» привязана к другому типу активности.\n"
                        f"При смене типа обязанность будет сброшена. Продолжить?",
                        parent=picker
                    ):
                        return
                    self.sheet.set_cell_data(row, 2, "")

            self.sheet.set_cell_data(row, 1, type_name)

            t_data = self.types_data.get(type_id)
            if t_data:
                def_role_id = t_data[3]
                def_sub_id = t_data[4]

                role_name = self.roles_id_to_name.get(def_role_id, "")
                sub_role_name = self.sub_roles_id_to_name.get(def_sub_id, "")

                self.sheet.set_cell_data(row, 3, role_name)
                self.sheet.set_cell_data(row, 4, sub_role_name)

            self._save_row(row)
            picker.destroy()

        tree.bind("<Double-Button-1>", select)
        tk.Button(picker, text="Выбрать", command=select).pack(pady=10)

    def _open_duty_picker(self, row):
        picker = tk.Toplevel(self)
        picker.transient(self.winfo_toplevel())
        picker.title("Выбор регулярной обязанности")

        picker.update_idletasks()
        screen_width = picker.winfo_screenwidth()
        screen_height = picker.winfo_screenheight()
        pos_x = (screen_width - 450) // 2
        pos_y = (screen_height - 500) // 2
        picker.geometry(f"450x500+{pos_x}+{pos_y}")
        picker.grab_set()

        current_type_name = self.sheet.get_cell_data(row, 1) or ""
        current_type_id = self.types_map.get(current_type_name)
        type_id_to_name = {v: k for k, v in self.types_map.items()}

        tree = ttk.Treeview(picker, columns=("id", "type", "period"), selectmode="browse")
        tree.heading("#0", text="Обязанность")
        tree.heading("id", text="ID")
        tree.heading("type", text="Тип активности")
        tree.heading("period", text="Период")
        tree.column("#0", width=200)
        tree.column("id", width=40, anchor="center")
        tree.column("type", width=120)
        tree.column("period", width=60, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        all_duties = self.duties_repo.get_all()
        for d in all_duties:
            d_id, d_name, d_type_id, d_period = d[0], d[1], d[5], d[6]
            if current_type_id is not None and d_type_id != current_type_id:
                continue
            tree.insert("", "end", text=d_name, values=(
                d_id, type_id_to_name.get(d_type_id, "?"), d_period
            ))

        def select(event=None):
            sel = tree.selection()
            if not sel:
                return
            item = tree.item(sel[0])
            d_name = item["text"]
            d_info = self.duties_data.get(d_name)
            if not d_info:
                return

            d_type_id = d_info["activity_type_id"]
            d_type_name = type_id_to_name.get(d_type_id, "")
            self.sheet.set_cell_data(row, 1, d_type_name)
            self.sheet.set_cell_data(row, 2, d_name)

            current_role = self.sheet.get_cell_data(row, 3) or ""
            current_sub = self.sheet.get_cell_data(row, 4) or ""

            if not current_sub and d_info["sub_role_id"]:
                sr_name = self.sub_roles_id_to_name.get(d_info["sub_role_id"], "")
                self.sheet.set_cell_data(row, 4, sr_name)
            if not current_role and d_info["role_id"]:
                r_name = self.roles_id_to_name.get(d_info["role_id"], "")
                self.sheet.set_cell_data(row, 3, r_name)

            self._save_row(row)
            picker.destroy()

        tree.bind("<Double-Button-1>", select)

        frame_btns = tk.Frame(picker)
        frame_btns.pack(fill="x", padx=10, pady=10)

        def clear_duty():
            self.sheet.set_cell_data(row, 2, "")
            self._save_row(row)
            picker.destroy()

        tk.Button(frame_btns, text="Очистить", command=clear_duty, fg="red").pack(side="left", padx=5)
        tk.Button(frame_btns, text="Выбрать", command=select).pack(side="right", padx=5)

    def _open_role_picker(self, row):
        picker = tk.Toplevel(self)
        picker.transient(self.winfo_toplevel())
        picker.title("Выбор роли / под-роли")

        picker.update_idletasks()
        screen_width = picker.winfo_screenwidth()
        screen_height = picker.winfo_screenheight()
        pos_x = (screen_width - 400) // 2
        pos_y = (screen_height - 500) // 2
        picker.geometry(f"400x500+{pos_x}+{pos_y}")
        picker.grab_set()

        tree = ttk.Treeview(picker, show="tree", selectmode="browse")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for r in sorted(self.roles_repo.get_all(), key=lambda x: x[0]):
            r_node = tree.insert("", "end", text=f"{r[0]}. {r[1]}")
            for sr in sorted(self.sub_roles_repo.get_by_parent(r[0]), key=lambda x: x[0]):
                tree.insert(r_node, "end", text=sr[1])

        def select(event=None):
            sel = tree.selection()
            if not sel:
                return
            item = tree.item(sel[0])
            parent_id = tree.parent(sel[0])

            if not parent_id:
                role_name = item["text"].split(". ", 1)[1]
                self.sheet.set_cell_data(row, 3, role_name)
                self.sheet.set_cell_data(row, 4, "")
            else:
                role_text = tree.item(parent_id)["text"]
                role_name = role_text.split(". ", 1)[1]
                self.sheet.set_cell_data(row, 3, role_name)
                self.sheet.set_cell_data(row, 4, item["text"])

            self._save_row(row)
            picker.destroy()

        tree.bind("<Double-Button-1>", select)
        tk.Button(picker, text="Выбрать", command=select).pack(pady=10)

    def on_cell_edited(self, event):
        row = event.row
        col = event.column
        if col in [0, 1, 2, 3, 4, 5, 6, 14, 15]:
            return
        self._save_row(row)
        self.refresh_table()

    def _save_row(self, row):
        try:
            act_id = str(self.sheet.get_cell_data(row, 0))
            type_name = self.sheet.get_cell_data(row, 1)
            duty_name = self.sheet.get_cell_data(row, 2) or ""
            role_name = self.sheet.get_cell_data(row, 3)
            sub_role_name = self.sheet.get_cell_data(row, 4)

            raw = self.raw_iso_data.get(act_id, {})
            start_time_iso = raw.get("start", "")
            end_time_iso = raw.get("end", "")

            # Длительности и вовлечённость: храним только то, что ввёл пользователь.
            # Пустая ячейка (или нечисловой мусор) → None → NULL в БД.
            # Ячейки НЕ перезаписываем: раньше здесь принудительно ставились
            # 0/0/0/100, и следующее сохранение затирало данные в базе.
            def _opt_int(value):
                s = str(value).strip() if value is not None else ""
                if s == "":
                    return None
                try:
                    return int(float(s))
                except (ValueError, TypeError):
                    return None

            duration = _opt_int(self.sheet.get_cell_data(row, 7))
            clean_duration = _opt_int(self.sheet.get_cell_data(row, 8))
            breaks_duration = _opt_int(self.sheet.get_cell_data(row, 9))
            engagement = _opt_int(self.sheet.get_cell_data(row, 10))

            try:
                est_val = str(self.sheet.get_cell_data(row, 11)).strip().lower()
                is_estimated = 1 if est_val in ["1", "true", "да", "yes", "истина"] else 0
            except Exception:
                is_estimated = 0
            self.sheet.set_cell_data(row, 11, is_estimated)

            source = self.sheet.get_cell_data(row, 12) or ""
            notes = self.sheet.get_cell_data(row, 13) or ""

            type_id = self.types_map.get(type_name)
            role_id = self.roles_map.get(role_name)
            sub_role_id = self.sub_roles_map.get(sub_role_name)
            regular_duty_id = self.duties_map.get(duty_name) if duty_name else None

            if not type_id:
                messagebox.showwarning("Ошибка", "Необходимо выбрать корректный Тип активности!")
                self.refresh_table()
                return

            self.activities_repo.update(
                int(act_id), type_id, role_id, sub_role_id, start_time_iso, end_time_iso,
                duration, clean_duration, breaks_duration, engagement, is_estimated, source, notes,
                regular_duty_id=regular_duty_id
            )

        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось сохранить:\n{e}")
            self.refresh_table()

    def on_add_row(self):
        if not self.types_map:
            messagebox.showwarning("Ошибка", "Сначала создайте хотя бы один тип активности!")
            return
        self._open_add_activity_dialog()

    def _open_add_activity_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Добавить активность")
        dialog.grab_set()

        # Геометрия: восстановить из prefs или дефолт по центру
        saved_geom = self.prefs_repo.get("manual_activity_dialog_geometry")
        if isinstance(saved_geom, str) and saved_geom.strip():
            try:
                dialog.geometry(saved_geom)
            except tk.TclError:
                dialog.geometry("900x750")
        else:
            dialog.update_idletasks()
            sw = dialog.winfo_screenwidth()
            sh = dialog.winfo_screenheight()
            w, h = 900, 750
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            dialog.geometry(f"{w}x{h}+{x}+{y}")

        roles_list = sorted(self.roles_repo.get_all(), key=lambda r: r[0])
        roles_display = {f"{r[0]}. {r[1]}": r[0] for r in roles_list}
        roles_id_to_display = {r[0]: f"{r[0]}. {r[1]}" for r in roles_list}

        paned = tk.PanedWindow(dialog, orient="horizontal",
                               sashwidth=8, sashrelief="raised")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # Восстановление позиции разделителя
        def _restore_sash():
            pos = self.prefs_repo.get("manual_activity_dialog_sash")
            if isinstance(pos, int):
                try:
                    paned.sash_place(0, pos, 0)
                except tk.TclError:
                    pass
        self.after(50, _restore_sash)

        def _save_sash(event=None):
            try:
                x, _ = paned.sash_coord(0)
                self.prefs_repo.set("manual_activity_dialog_sash", x)
            except Exception:
                pass
        paned.bind("<ButtonRelease-1>", _save_sash)

        # --- Левая панель: дерево ---
        left = tk.Frame(paned)
        paned.add(left, stretch="never", width=250)

        left_header = tk.Frame(left)
        left_header.pack(fill="x")
        tk.Label(left_header, text="Роли / Под-роли:",
                 font=("Arial", 10, "bold")).pack(side="left")

        btns_header = tk.Frame(left)
        btns_header.pack(fill="x", pady=2)

        tree_roles = ttk.Treeview(left, show="tree", selectmode="browse")
        tree_roles.column("#0", width=230, minwidth=180)

        right = tk.Frame(paned)
        paned.add(right, stretch="always")

        state = self.prefs_repo.get("roles_tree_state")
        if not isinstance(state, dict):
            state = {}

        def _load_tree():
            for item in tree_roles.get_children():
                tree_roles.delete(item)
            tree_roles.insert("", "end", iid="root", text="📁 Все роли", open=True)
            for r in roles_list:
                rid, name = r[0], r[1]
                is_open = state.get(str(rid), True)
                tree_roles.insert("root", "end", iid=f"role_{rid}",
                                  text=f"{rid}. {name}", open=is_open,
                                  tags=("role_node",))
                for sr in sorted(self.sub_roles_repo.get_by_parent(rid), key=lambda x: x[0]):
                    tree_roles.insert(f"role_{rid}", "end",
                                      iid=f"sub_{sr[0]}", text=sr[1],
                                      tags=("sub_role_node",))
            tree_roles.tag_configure("role_node", font=("Arial", 11, "bold"))
            tree_roles.tag_configure("sub_role_node", font=("Arial", 10, "normal"))

        def _on_node_toggle(event=None):
            new_state = dict(state)
            for r in roles_list:
                rid = r[0]
                iid = f"role_{rid}"
                if tree_roles.exists(iid):
                    new_state[str(rid)] = bool(tree_roles.item(iid, "open"))
            state.clear()
            state.update(new_state)
            self.prefs_repo.set("roles_tree_state", state)

        def _expand_all():
            for r in roles_list:
                if tree_roles.exists(f"role_{r[0]}"):
                    tree_roles.item(f"role_{r[0]}", open=True)
            tree_roles.item("root", open=True)
            new_state = {str(r[0]): True for r in roles_list}
            state.clear()
            state.update(new_state)
            self.prefs_repo.set("roles_tree_state", state)

        def _collapse_all():
            for r in roles_list:
                if tree_roles.exists(f"role_{r[0]}"):
                    tree_roles.item(f"role_{r[0]}", open=False)
            tree_roles.item("root", open=True)
            new_state = {str(r[0]): False for r in roles_list}
            state.clear()
            state.update(new_state)
            self.prefs_repo.set("roles_tree_state", state)

        tk.Button(btns_header, text="Развернуть", font=("Arial", 8),
                  command=_expand_all).pack(side="left", padx=2)
        tk.Button(btns_header, text="Свернуть", font=("Arial", 8),
                  command=_collapse_all).pack(side="left", padx=2)

        tree_roles.pack(fill="both", expand=True, pady=2)
        tree_roles.bind("<<TreeviewOpen>>", _on_node_toggle)
        tree_roles.bind("<<TreeviewClose>>", _on_node_toggle)

        _load_tree()

        # --- Правая панель: форма (в скролле) ---
        canvas = tk.Canvas(right, highlightthickness=0)
        sb = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)

        form_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=form_frame, anchor="nw")
        form_frame.bind("<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(1, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tk.Label(form_frame, text="Тип активности *:",
                 font=("Arial", 10, "bold")).pack(fill="x", padx=15, pady=(10, 0))
        cb_type = ttk.Combobox(form_frame, state="readonly", width=40)
        cb_type.pack(fill="x", padx=15, pady=2)

        tk.Label(form_frame, text="Обязанность:",
                 font=("Arial", 10, "bold")).pack(fill="x", padx=15, pady=(10, 0))
        cb_duty = ttk.Combobox(form_frame, state="readonly", width=40)
        cb_duty.pack(fill="x", padx=15, pady=2)

        tk.Label(form_frame, text="Роль:",
                 font=("Arial", 10, "bold")).pack(fill="x", padx=15, pady=(10, 0))
        cb_role = ttk.Combobox(form_frame, state="readonly", width=40)
        cb_role['values'] = list(roles_display.keys())
        cb_role.pack(fill="x", padx=15, pady=2)

        tk.Label(form_frame, text="Подроль:",
                 font=("Arial", 10, "bold")).pack(fill="x", padx=15, pady=(10, 0))
        cb_sub = ttk.Combobox(form_frame, state="readonly", width=40)
        cb_sub.pack(fill="x", padx=15, pady=2)

        tk.Label(form_frame, text="Дата:",
                 font=("Arial", 10, "bold")).pack(pady=(10, 0))
        today_dt = datetime_utils.to_datetime(datetime_utils.get_now_iso())
        cal = DateEntry(form_frame, width=12, background='darkblue',
                        foreground='white', borderwidth=2,
                        year=today_dt.year, month=today_dt.month, day=today_dt.day,
                        locale='ru_RU')
        cal.pack(pady=2)

        tk.Label(form_frame, text="Время начала *:",
                 font=("Arial", 10, "bold")).pack(pady=(10, 2))

        max_end = self.activities_repo.get_max_end_time_for_date(today_dt.strftime("%Y-%m-%d"))
        if max_end:
            dt_max = datetime_utils.to_datetime(max_end)
            init_start_h = dt_max.strftime("%H")
            init_start_m = dt_max.strftime("%M")
        else:
            init_start_h = "10"
            init_start_m = "00"

        frame_start = tk.Frame(form_frame)
        frame_start.pack()

        var_start_h = tk.StringVar(value=init_start_h)
        var_start_m = tk.StringVar(value=init_start_m)
        tk.Spinbox(frame_start, from_=0, to=23, width=3, textvariable=var_start_h,
                   format="%02.0f", font=("Arial", 11)).pack(side="left", padx=2)
        tk.Label(frame_start, text=":", font=("Arial", 11, "bold")).pack(side="left")
        tk.Spinbox(frame_start, from_=0, to=59, width=3, textvariable=var_start_m,
                   format="%02.0f", font=("Arial", 11)).pack(side="left", padx=2)

        tk.Label(form_frame, text="Время окончания (можно оставить пустым):",
                 font=("Arial", 10, "bold")).pack(pady=(10, 2))
        frame_end = tk.Frame(form_frame)
        frame_end.pack()

        var_end_h = tk.StringVar(value=today_dt.strftime("%H"))
        var_end_m = tk.StringVar(value=today_dt.strftime("%M"))
        spin_end_h = tk.Spinbox(frame_end, from_=0, to=23, width=3, textvariable=var_end_h,
                                format="%02.0f", font=("Arial", 11))
        spin_end_h.pack(side="left", padx=2)
        tk.Label(frame_end, text=":", font=("Arial", 11, "bold")).pack(side="left")
        spin_end_m = tk.Spinbox(frame_end, from_=0, to=59, width=3, textvariable=var_end_m,
                                format="%02.0f", font=("Arial", 11))
        spin_end_m.pack(side="left", padx=2)

        def set_start_now():
            now = datetime_utils.to_datetime(datetime_utils.get_now_iso())
            var_start_h.set(now.strftime("%H"))
            var_start_m.set(now.strftime("%M"))
            spin_end_h.delete(0, "end")
            spin_end_m.delete(0, "end")
            var_end_h.set("")
            var_end_m.set("")

        tk.Button(frame_start, text="Установить текущее",
                  command=set_start_now, font=("Arial", 8)).pack(side="left", padx=(12, 0))

        tk.Label(form_frame, text="Заметки:").pack(anchor="w", padx=15, pady=(10, 2))
        ent_notes = tk.Entry(form_frame, width=50)
        ent_notes.pack(fill="x", padx=15, pady=2)

        filter_state = {"role_id": None, "sub_role_id": None}
        duties_state = {"duties_map": {}}

        def _types_for_filter() -> dict:
            if filter_state["sub_role_id"] is not None:
                sr = filter_state["sub_role_id"]
                return {t[1]: t[0] for t in self.types_repo.get_all() if t[4] == sr}
            if filter_state["role_id"] is not None:
                r = filter_state["role_id"]
                subs_of_r = {s[0] for s in self.sub_roles_repo.get_by_parent(r)}
                return {t[1]: t[0] for t in self.types_repo.get_all()
                        if t[3] == r or t[4] in subs_of_r}
            return dict(self.types_map)

        def _refresh_duties_for_type():
            type_name = cb_type.get()
            type_id = self.types_map.get(type_name) if type_name else None
            relevant = []
            map_by_name = {}
            for d in self.duties_repo.get_all():
                d_id, d_name, d_type_id = d[0], d[1], d[5]
                if type_id is None or d_type_id == type_id:
                    relevant.append(d_name)
                    map_by_name[d_name] = d_id
            duties_state["duties_map"] = map_by_name
            cb_duty['values'] = relevant
            cb_duty.set("")

        def _refresh_subs_for_role(role_display):
            if not role_display:
                cb_sub['values'] = []
                cb_sub.set("")
                return
            role_id = roles_display.get(role_display)
            if role_id is None:
                cb_sub['values'] = []
                cb_sub.set("")
                return
            subs = sorted(self.sub_roles_repo.get_by_parent(role_id), key=lambda x: x[0])
            cb_sub['values'] = [s[1] for s in subs]
            cb_sub.set("")

        def _apply_type_change_defaults():
            type_name = cb_type.get()
            type_id = self.types_map.get(type_name) if type_name else None
            _refresh_duties_for_type()

            if filter_state["sub_role_id"] is not None:
                return

            if filter_state["role_id"] is not None:
                if type_id:
                    t_data = self.types_data.get(type_id)
                    if t_data:
                        def_sub_id = t_data[4]
                        if def_sub_id:
                            for sub in self.sub_roles_repo.get_by_parent(filter_state["role_id"]):
                                if sub[0] == def_sub_id:
                                    cb_sub.set(sub[1])
                                    return
                        cb_sub.set("")
                else:
                    cb_sub.set("")
                return

            cb_role.set("")
            cb_sub.set("")
            if type_id:
                t_data = self.types_data.get(type_id)
                if t_data:
                    def_role_id = t_data[3]
                    def_sub_id = t_data[4]
                    if def_role_id:
                        cb_role.set(roles_id_to_display.get(def_role_id, ""))
                        _refresh_subs_for_role(cb_role.get())
                    if def_sub_id:
                        sr_name = self.sub_roles_id_to_name.get(def_sub_id, "")
                        cb_sub.set(sr_name)

        def _apply_duty_change(event=None):
            duty_name = cb_duty.get()
            if not duty_name:
                return
            d_id = duties_state["duties_map"].get(duty_name)
            if d_id is None:
                return
            d = next((x for x in self.duties_repo.get_all() if x[0] == d_id), None)
            if not d:
                return
            d_type_id = d[5]
            d_role_id = d[7]
            d_sub_id = d[8]

            for tname, tid in self.types_map.items():
                if tid == d_type_id:
                    cb_type.set(tname)
                    break

            _refresh_duties_for_type()
            cb_duty.set(duty_name)

            if filter_state["sub_role_id"] is not None:
                return
            if filter_state["role_id"] is not None:
                cb_sub.set("")
                if d_sub_id:
                    for sub in self.sub_roles_repo.get_by_parent(filter_state["role_id"]):
                        if sub[0] == d_sub_id:
                            cb_sub.set(sub[1])
                            break
                return
            cb_role.set("")
            cb_sub.set("")
            if d_role_id:
                cb_role.set(roles_id_to_display.get(d_role_id, ""))
                _refresh_subs_for_role(cb_role.get())
            if d_sub_id:
                sr_name = self.sub_roles_id_to_name.get(d_sub_id, "")
                cb_sub.set(sr_name)

        def _on_role_change(event=None):
            _refresh_subs_for_role(cb_role.get())

        def _on_sub_change(event=None):
            sub_name = cb_sub.get()
            if not sub_name:
                return
            sub_id = self.sub_roles_map.get(sub_name)
            if sub_id is None:
                return
            for r in roles_list:
                subs = self.sub_roles_repo.get_by_parent(r[0])
                if any(s[0] == sub_id for s in subs):
                    cb_role.set(roles_id_to_display.get(r[0], ""))
                    break

        def _apply_filter():
            sel = tree_roles.selection()
            if not sel:
                tree_roles.selection_set("root")
                return
            iid = sel[0]
            if iid == "root":
                filter_state["role_id"] = None
                filter_state["sub_role_id"] = None
                cb_role.config(state="readonly")
                cb_sub.config(state="readonly")
                _refresh_subs_for_role(cb_role.get())
            elif iid.startswith("role_"):
                rid = int(iid.replace("role_", ""))
                filter_state["role_id"] = rid
                filter_state["sub_role_id"] = None
                cb_role.set(roles_id_to_display.get(rid, ""))
                cb_role.config(state="disabled")
                cb_sub.config(state="readonly")
                subs = sorted(self.sub_roles_repo.get_by_parent(rid), key=lambda x: x[0])
                cb_sub['values'] = [s[1] for s in subs]
                cb_sub.set("")
            else:
                srid = int(iid.replace("sub_", ""))
                filter_state["sub_role_id"] = srid
                parent_rid = None
                for r in roles_list:
                    subs = self.sub_roles_repo.get_by_parent(r[0])
                    if any(s[0] == srid for s in subs):
                        parent_rid = r[0]
                        break
                filter_state["role_id"] = parent_rid
                if parent_rid is not None:
                    cb_role.set(roles_id_to_display.get(parent_rid, ""))
                cb_role.config(state="disabled")
                cb_sub.set(self.sub_roles_id_to_name.get(srid, ""))
                cb_sub.config(state="disabled")

            types_for_filter = _types_for_filter()
            cb_type['values'] = list(types_for_filter.keys())
            if cb_type.get() not in types_for_filter:
                cb_type.set("")

            _apply_type_change_defaults()

        tree_roles.bind("<<TreeviewSelect>>", lambda e: _apply_filter())
        cb_type.bind("<<ComboboxSelected>>", lambda e: _apply_type_change_defaults())
        cb_duty.bind("<<ComboboxSelected>>", _apply_duty_change)
        cb_role.bind("<<ComboboxSelected>>", _on_role_change)
        cb_sub.bind("<<ComboboxSelected>>", _on_sub_change)

        # Начальное состояние: корень, форма пустая (тип не выбран)
        tree_roles.selection_set("root")
        _apply_filter()

        # --- Сохранение геометрии и закрытие ---
        def _save_geometry_and_close():
            try:
                self.prefs_repo.set("manual_activity_dialog_geometry", dialog.geometry())
            except Exception:
                pass
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", _save_geometry_and_close)

        def apply():
            type_name = cb_type.get()
            type_id = self.types_map.get(type_name)
            if not type_id:
                messagebox.showerror("Ошибка", "Выберите тип активности", parent=dialog)
                return

            try:
                sh = int(var_start_h.get())
                sm = int(var_start_m.get())
            except (ValueError, TypeError):
                messagebox.showerror("Ошибка", "Введите корректное время начала", parent=dialog)
                return
            if not (0 <= sh <= 23 and 0 <= sm <= 59):
                messagebox.showerror("Ошибка", "Часы 0-23, минуты 0-59", parent=dialog)
                return

            sd = cal.get_date()
            start_iso = f"{sd.year}-{sd.month:02d}-{sd.day:02d}T{sh:02d}:{sm:02d}:00+03:00"

            end_h_str = str(var_end_h.get()).strip()
            end_m_str = str(var_end_m.get()).strip()

            if end_h_str == "" and end_m_str == "":
                end_iso = None
                duration = 0
            elif end_h_str == "" or end_m_str == "":
                messagebox.showerror("Ошибка",
                    "Заполните оба поля времени окончания или оставьте оба пустыми", parent=dialog)
                return
            else:
                try:
                    eh = int(end_h_str)
                    em = int(end_m_str)
                except (ValueError, TypeError):
                    messagebox.showerror("Ошибка", "Введите корректное время окончания", parent=dialog)
                    return
                if not (0 <= eh <= 23 and 0 <= em <= 59):
                    messagebox.showerror("Ошибка", "Часы 0-23, минуты 0-59", parent=dialog)
                    return
                end_iso = f"{sd.year}-{sd.month:02d}-{sd.day:02d}T{eh:02d}:{em:02d}:00+03:00"
                if end_iso <= start_iso:
                    messagebox.showerror("Ошибка", "Конец должен быть позже начала", parent=dialog)
                    return
                start_dt = datetime_utils.to_datetime(start_iso)
                end_dt = datetime_utils.to_datetime(end_iso)
                duration = int((end_dt - start_dt).total_seconds() / 60)

            role_name = cb_role.get()
            role_id = roles_display.get(role_name) if role_name else None
            sub_role_id = self.sub_roles_map.get(cb_sub.get()) if cb_sub.get() else None
            duty_id = duties_state["duties_map"].get(cb_duty.get()) if cb_duty.get() else None

            try:
                self.activities_repo.add(
                    type_id=type_id,
                    role_id=role_id,
                    sub_role_id=sub_role_id,
                    start_time=start_iso,
                    end_time=end_iso,
                    duration=None,
                    clean_duration=None,
                    breaks_duration=None,
                    engagement=None,
                    is_estimated=0,
                    source="manual",
                    notes=ent_notes.get().strip(),
                    regular_duty_id=duty_id,
                )
            except Exception as e:
                messagebox.showerror("Ошибка БД", f"Не удалось добавить активность:\n{e}", parent=dialog)
                return

            _save_geometry_and_close()
            self.refresh_table()

        frame_btns = tk.Frame(form_frame)
        frame_btns.pack(pady=15)
        tk.Button(frame_btns, text="Создать", command=apply, width=15).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=_save_geometry_and_close, width=10).pack(side="left", padx=5)

    def on_delete_row(self):
        selected = self.sheet.get_currently_selected()
        row = getattr(selected, "row", None)
        if row is None:
            return
        act_id = self.sheet.get_cell_data(row, 0)
        if messagebox.askyesno("Подтверждение", "Удалить выбранную активность?"):
            try:
                self.activities_repo.delete(act_id)
                self.refresh_table()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить:\n{e}")