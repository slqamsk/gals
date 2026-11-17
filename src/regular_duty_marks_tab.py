# src/regular_duty_marks_tab.py
# Вкладка «Выполнение обязанностей»: список обязанностей за период,
# отметки о выполнении, список активностей по каждой обязанности.

import tkinter as tk
from tkinter import ttk, messagebox
from tkcalendar import DateEntry
from tksheet import Sheet

from . import datetime_utils
from .ui_utils import format_period_label
from .regular_duty_marks_repo import RegularDutyMarksRepository
from .period_repo import PeriodRepository


class RegularDutyMarksTab(tk.Frame):
    MODE_DAY = "day"
    MODE_WEEK = "week"
    MODE_MONTH = "month"
    VALID_MODES = (MODE_DAY, MODE_WEEK, MODE_MONTH)

    def __init__(self, parent, activities_repo, types_repo, duties_repo,
                 roles_repo, sub_roles_repo, prefs_repo):
        super().__init__(parent)
        self.activities_repo = activities_repo
        self.types_repo = types_repo
        self.duties_repo = duties_repo
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.prefs_repo = prefs_repo

        self.marks_repo = RegularDutyMarksRepository(activities_repo.db)
        self.period_repo = PeriodRepository(activities_repo.db)

        self.current_mode = None
        self.current_period_id = None
        self.current_period_value = None
        self.current_period_meta = None
        self._current_periods = []
        self.selected_duty_id = None

        self.duties = []
        self.duty_items = {}
        self.current_marks = {}
        self.types_map = {}
        self.roles_map = {}
        self.roles_id_to_name = {}
        self.sub_roles_map = {}
        self.sub_roles_id_to_name = {}

        self.sort_col = self.prefs_repo.get("duty_marks_sort_col") or "order"
        self.sort_asc = self.prefs_repo.get("duty_marks_sort_asc")
        if self.sort_asc is None:
            self.sort_asc = True

        self._suppress_events = False

        self._build_ui()
        self._restore_state()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        # --- Верхняя панель ---
        frame_top = tk.Frame(self)
        frame_top.pack(fill="x", padx=10, pady=5)

        tk.Label(frame_top, text="Режим:").pack(side="left")
        self.cb_mode = ttk.Combobox(
            frame_top, state="readonly", width=10,
            values=[self.MODE_DAY, self.MODE_WEEK, self.MODE_MONTH]
        )
        self.cb_mode.pack(side="left", padx=5)
        self.cb_mode.bind("<<ComboboxSelected>>", self._on_mode_changed)

        tk.Label(frame_top, text="Период:").pack(side="left", padx=(15, 0))
        self.cb_period = ttk.Combobox(frame_top, state="readonly", width=45)
        self.cb_period.pack(side="left", padx=5)
        self.cb_period.bind("<<ComboboxSelected>>", self._on_period_changed)

        self.layout_var = tk.StringVar(value="left_right")
        tk.Radiobutton(frame_top, text="Слева-справа", variable=self.layout_var,
                       value="left_right", command=self._on_layout_change).pack(side="left", padx=(15, 0))
        tk.Radiobutton(frame_top, text="Сверху-снизу", variable=self.layout_var,
                       value="top_bottom", command=self._on_layout_change).pack(side="left", padx=5)

        self.btn_refresh = tk.Button(frame_top, text="Обновить", command=self.refresh_table)
        self.btn_refresh.pack(side="left", padx=5)

        # --- PanedWindow ---
        self.paned = tk.PanedWindow(self, orient="horizontal", sashwidth=5, sashrelief="raised")
        self.paned.pack(fill="both", expand=True, padx=10, pady=5)

        # --- Левая панель: список обязанностей ---
        self.frame_left = tk.Frame(self.paned)
        self.paned.add(self.frame_left, stretch="always")

        tk.Label(self.frame_left, text="Обязанности за период:").pack(anchor="w")

        self.tree = ttk.Treeview(
            self.frame_left,
            columns=("order", "name", "id", "type", "importance", "status"),
            show="headings",
            selectmode="browse"
        )
        self.tree.heading("order", text="Порядок", command=lambda: self._on_header_click("order"))
        self.tree.heading("name", text="Обязанность", command=lambda: self._on_header_click("name"))
        self.tree.heading("id", text="ID", command=lambda: self._on_header_click("id"))
        self.tree.heading("type", text="Тип активности", command=lambda: self._on_header_click("type"))
        self.tree.heading("importance", text="Важность", command=lambda: self._on_header_click("importance"))
        self.tree.heading("status", text="Статус", command=lambda: self._on_header_click("status"))

        self.tree.column("order", width=70, anchor="center")
        self.tree.column("name", width=200)
        self.tree.column("id", width=40, anchor="center")
        self.tree.column("type", width=130)
        self.tree.column("importance", width=80, anchor="center")
        self.tree.column("status", width=120)

        self.tree.pack(fill="both", expand=True, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self._on_duty_select)

        # --- Правая панель ---
        self.frame_right = tk.Frame(self.paned)
        self.paned.add(self.frame_right, stretch="always")

        frame_details = tk.LabelFrame(self.frame_right, text="Детали обязанности", padx=5, pady=5)
        frame_details.pack(fill="x", padx=5, pady=(0, 5))

        self.lbl_duty_name = tk.Label(frame_details, text="—",
                                      font=("Arial", 11, "bold"), anchor="w")
        self.lbl_duty_name.pack(fill="x")

        self.lbl_duty_type = tk.Label(frame_details, text="", anchor="w", fg="#555")
        self.lbl_duty_type.pack(fill="x")

        self.lbl_duty_role = tk.Label(frame_details, text="", anchor="w", fg="#555")
        self.lbl_duty_role.pack(fill="x")

        self.lbl_duty_status = tk.Label(frame_details, text="", anchor="w", fg="#333")
        self.lbl_duty_status.pack(fill="x")

        frame_btns = tk.Frame(frame_details)
        frame_btns.pack(fill="x", pady=(5, 0))

        self.btn_mark = tk.Button(frame_btns, text="Отметить выполнение",
                                  command=self._open_mark_dialog, state="disabled")
        self.btn_mark.pack(side="left", padx=(0, 5))

        self.btn_unmark = tk.Button(frame_btns, text="Снять отметку",
                                    command=self._on_unmark, state="disabled", fg="red")
        self.btn_unmark.pack(side="left", padx=5)

        self.btn_add_activity = tk.Button(frame_btns, text="Добавить активность",
                                          command=self._open_add_activity_dialog, state="disabled")
        self.btn_add_activity.pack(side="right", padx=5)

        frame_activities = tk.LabelFrame(self.frame_right, text="Активности за период", padx=5, pady=5)
        frame_activities.pack(fill="both", expand=True, padx=5, pady=5)

        self.sheet_activities = Sheet(
            frame_activities,
            headers=["ID", "Начало", "Конец", "Длит. (мин)", "Заметки"],
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
        self.sheet_activities.pack(fill="both", expand=True)
        self.sheet_activities.enable_bindings("all")
        self.sheet_activities.readonly_columns(columns=[0, 1, 2, 3, 4])
        self.sheet_activities.set_column_widths([50, 140, 140, 80, 250])
        self.sheet_activities.MT.bind("<Double-Button-1>", self._on_activity_double_click, add="+")

    # ------------------------------------------------------------------
    # Восстановление / сохранение состояния
    # ------------------------------------------------------------------
    def _restore_state(self):
        saved_mode = self.prefs_repo.get("duty_marks_mode")
        if saved_mode not in self.VALID_MODES:
            saved_mode = self.MODE_WEEK
        self.current_mode = saved_mode
        self.cb_mode.set(saved_mode)

        saved_layout = self.prefs_repo.get("duty_marks_layout")
        if saved_layout in ("left_right", "top_bottom"):
            self.layout_var.set(saved_layout)
        self._apply_layout()

        self._refresh_periods()

    def _apply_layout(self):
        if self.layout_var.get() == "top_bottom":
            self.paned.configure(orient="vertical")
        else:
            self.paned.configure(orient="horizontal")

    def _on_layout_change(self):
        self.prefs_repo.set("duty_marks_layout", self.layout_var.get())
        self._apply_layout()

    def _get_saved_period(self, mode: str):
        saved = self.prefs_repo.get("duty_marks_periods")
        if isinstance(saved, dict):
            return saved.get(mode)
        return None

    def _save_period(self, mode: str, period_value: str):
        saved = self.prefs_repo.get("duty_marks_periods")
        if not isinstance(saved, dict):
            saved = {}
        saved = dict(saved)
        saved[mode] = period_value
        self.prefs_repo.set("duty_marks_periods", saved)

    def save_state(self):
        self.prefs_repo.set("duty_marks_layout", self.layout_var.get())
        self.prefs_repo.set("duty_marks_mode", self.current_mode)
        self.prefs_repo.set("duty_marks_sort_col", self.sort_col)
        self.prefs_repo.set("duty_marks_sort_asc", self.sort_asc)
        if self.current_period_value:
            self._save_period(self.current_mode, self.current_period_value)

    # ------------------------------------------------------------------
    # Обработчики верхней панели
    # ------------------------------------------------------------------
    def _on_header_click(self, col):
        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True
        self.save_state()
        self._load_duties()

    def _on_mode_changed(self, event=None):
        if self._suppress_events:
            return
        new_mode = self.cb_mode.get()
        if new_mode == self.current_mode or new_mode not in self.VALID_MODES:
            return
        self.current_mode = new_mode
        self.prefs_repo.set("duty_marks_mode", new_mode)
        self.selected_duty_id = None
        self._refresh_periods()

    def _on_period_changed(self, event=None):
        if self._suppress_events:
            return
        idx = self.cb_period.current()
        if idx < 0 or idx >= len(self._current_periods):
            return
        period = self._current_periods[idx]
        self.current_period_id = period[0]
        self.current_period_value = period[1]
        self._save_period(self.current_mode, self.current_period_value)
        self.current_period_meta = self.period_repo.get_period_meta(self.current_period_id)
        self._load_data()

    def refresh_table(self):
        self._refresh_periods()

    # ------------------------------------------------------------------
    # Загрузка данных
    # ------------------------------------------------------------------
    def _refresh_periods(self):
        self._suppress_events = True
        try:
            mode = self.current_mode
            periods = self.period_repo.get_available_periods(mode)
            self._current_periods = periods

            labels = [format_period_label(mode, p) for p in periods]
            self.cb_period['values'] = labels

            if not periods:
                self.cb_period.set("")
                self.current_period_id = None
                self.current_period_value = None
                self.current_period_meta = None
                self.current_marks = {}
                self._load_duties()
                self._clear_details()
                return

            saved_value = self._get_saved_period(mode)
            selected_idx = 0
            if saved_value:
                for i, p in enumerate(periods):
                    if p[1] == saved_value:
                        selected_idx = i
                        break

            self.cb_period.current(selected_idx)
            self.current_period_id = periods[selected_idx][0]
            self.current_period_value = periods[selected_idx][1]
            self.current_period_meta = self.period_repo.get_period_meta(self.current_period_id)

            self.current_marks = self.marks_repo.get_all_for_period(self.current_period_id)

            self._load_duties()

            if self.selected_duty_id:
                self._show_duty_details(self.selected_duty_id)
            else:
                self._clear_details()
        finally:
            self._suppress_events = False

    def _load_data(self):
        if self.current_period_id is not None:
            self.current_marks = self.marks_repo.get_all_for_period(self.current_period_id)
        else:
            self.current_marks = {}

        self._update_tree_statuses()

        if self.selected_duty_id:
            self._show_duty_details(self.selected_duty_id)
        else:
            self._clear_details()

    def _load_duties(self):
        self.types_map = {t[0]: t[1] for t in self.types_repo.get_all()}
        self.roles_map = {r[0]: r[1] for r in self.roles_repo.get_all()}
        self.sub_roles_map = {}
        for r in self.roles_repo.get_all():
            for sr in self.sub_roles_repo.get_by_parent(r[0]):
                self.sub_roles_map[sr[0]] = sr[1]

        prev_selected = self.selected_duty_id

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.duty_items = {}

        rows = self.duties_repo.get_by_period_type(self.current_mode)
        self.duties = []
        for r in rows:
            self.duties.append({
                "id": r[0],
                "name": r[1],
                "execution_order": r[2],
                "importance": r[3],
                "activity_type_id": r[4],
                "role_id": r[5],
                "sub_role_id": r[6]
            })

        def get_sort_key(d):
            col = self.sort_col
            if col == "order":
                return (d["execution_order"] is None,
                        d["execution_order"] if d["execution_order"] is not None else 0)
            if col == "id":
                return (False, d["id"])
            if col == "name":
                return (False, d["name"].lower())
            if col == "type":
                return (False, self.types_map.get(d["activity_type_id"], "").lower())
            if col == "importance":
                return (d["importance"] is None,
                        d["importance"] if d["importance"] is not None else 0)
            if col == "status":
                mark = self.current_marks.get(d["id"])
                raw = mark["status"] if mark else None
                if raw is None:
                    return (True, "")
                order = {"done": 0, "partial": 1, "not_done": 2}
                return (False, order.get(raw, 99))
            return (False, "")

        self.duties.sort(key=get_sort_key, reverse=not self.sort_asc)

        for d in self.duties:
            d_id = d["id"]
            d_name = d["name"]
            type_name = self.types_map.get(d["activity_type_id"], "")
            mark = self.current_marks.get(d_id)
            status = self._format_mark_status(mark)

            ord_disp = d["execution_order"] if d["execution_order"] is not None else ""
            imp_disp = d["importance"] if d["importance"] is not None else ""

            self.tree.insert(
                "", "end", iid=str(d_id),
                values=(ord_disp, d_name, d_id, type_name, imp_disp, status)
            )
            self.duty_items[d_id] = str(d_id)

        if prev_selected and prev_selected in self.duty_items:
            self.tree.selection_set(str(prev_selected))
            self.tree.focus(str(prev_selected))
            self.selected_duty_id = prev_selected
        elif self.duty_items:
            first_id = list(self.duty_items.keys())[0]
            self.tree.selection_set(str(first_id))
            self.tree.focus(str(first_id))
            self.selected_duty_id = first_id
        else:
            self.selected_duty_id = None

    def _update_tree_statuses(self):
        for d in self.duties:
            d_id = d["id"]
            if d_id not in self.duty_items:
                continue
            item_id = self.duty_items[d_id]
            mark = self.current_marks.get(d_id)
            status = self._format_mark_status(mark)
            try:
                self.tree.set(item_id, "status", status)
            except tk.TclError:
                pass

    def _format_mark_status(self, mark) -> str:
        if not mark:
            return "—"
        status = mark["status"]
        value = mark["mark_value"]
        if status == "done":
            return "✓ Выполнено"
        if status == "not_done":
            return "✗ Не выполнено"
        return f"~ {value}%"

    # ------------------------------------------------------------------
    # Детали выбранной обязанности
    # ------------------------------------------------------------------
    def _on_duty_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            self.selected_duty_id = None
            self._clear_details()
            return
        try:
            self.selected_duty_id = int(sel[0])
        except ValueError:
            self.selected_duty_id = None
            self._clear_details()
            return
        self._show_duty_details(self.selected_duty_id)

    def _show_duty_details(self, duty_id: int):
        duty = next((d for d in self.duties if d["id"] == duty_id), None)
        if not duty:
            self._clear_details()
            return

        d_name = duty["name"]
        d_type_id = duty["activity_type_id"]
        d_role_id = duty["role_id"]
        d_sub_id = duty["sub_role_id"]

        type_name = self.types_map.get(d_type_id, "")
        role_name = self.roles_map.get(d_role_id, "")
        sub_name = self.sub_roles_map.get(d_sub_id, "")

        self.lbl_duty_name.config(text=d_name)
        self.lbl_duty_type.config(text=f"Тип активности: {type_name}")

        role_text = "Роль: —"
        if role_name:
            role_text = f"Роль: {role_name}"
            if sub_name:
                role_text += f" / {sub_name}"
        self.lbl_duty_role.config(text=role_text)

        mark = self.current_marks.get(duty_id)
        status = self._format_mark_status(mark)
        self.lbl_duty_status.config(text=f"Статус за период: {status}")

        self.btn_mark.config(state="normal")
        self.btn_unmark.config(state="normal" if mark else "disabled")
        self.btn_add_activity.config(state="normal")

        if self.current_period_meta:
            fs = self.current_period_meta[4]
            fe = self.current_period_meta[5]
            activities = self.activities_repo.get_by_duty_and_period(duty_id, fs, fe)
            data = []
            for a in activities:
                a_id, a_start, a_end, a_dur, a_notes = a
                data.append([
                    a_id,
                    datetime_utils.to_display(a_start) if a_start else "",
                    datetime_utils.to_display(a_end) if a_end else "",
                    a_dur if a_dur is not None else "",
                    a_notes or "",
                ])
            self.sheet_activities.set_sheet_data(data, reset_col_positions=False)
        else:
            self.sheet_activities.set_sheet_data([], reset_col_positions=False)

    def _clear_details(self):
        self.lbl_duty_name.config(text="—")
        self.lbl_duty_type.config(text="")
        self.lbl_duty_role.config(text="")
        self.lbl_duty_status.config(text="")
        self.btn_mark.config(state="disabled")
        self.btn_unmark.config(state="disabled")
        self.btn_add_activity.config(state="disabled")
        self.sheet_activities.set_sheet_data([], reset_col_positions=False)

    # ------------------------------------------------------------------
    # Отметка выполнения (отдельный диалог)
    # ------------------------------------------------------------------
    def _open_mark_dialog(self):
        if not self.selected_duty_id or self.current_period_id is None:
            return

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Отметка о выполнении")
        dialog.geometry("340x320+400+200")
        dialog.grab_set()

        tk.Label(dialog, text="Выберите статус:",
                 font=("Arial", 10, "bold")).pack(pady=(15, 5))

        status_var = tk.StringVar(value="done")

        tk.Radiobutton(dialog, text="✓ Выполнено полностью (100%)",
                       variable=status_var, value="done").pack(anchor="w", padx=30, pady=2)
        tk.Radiobutton(dialog, text="✗ Не выполнено (0%)",
                       variable=status_var, value="not_done").pack(anchor="w", padx=30, pady=2)
        tk.Radiobutton(dialog, text="~ Выполнено частично:",
                       variable=status_var, value="partial").pack(anchor="w", padx=30, pady=2)

        frame_partial = tk.Frame(dialog)
        frame_partial.pack(fill="x", padx=60, pady=(0, 10))

        partial_var = tk.StringVar(value="50")
        entry_partial = tk.Entry(frame_partial, textvariable=partial_var, width=10, state="disabled")
        entry_partial.pack(side="left")
        tk.Label(frame_partial, text="% (1-99)").pack(side="left", padx=5)

        def on_status_change():
            if status_var.get() == "partial":
                entry_partial.config(state="normal")
            else:
                entry_partial.config(state="disabled")

        for rb in dialog.winfo_children():
            if isinstance(rb, tk.Radiobutton):
                rb.config(command=on_status_change)

        tk.Label(dialog, text="Комментарий (опционально):").pack(anchor="w", padx=20, pady=(10, 2))
        note_var = tk.StringVar()
        tk.Entry(dialog, textvariable=note_var, width=40).pack(padx=20, pady=2)

        def apply():
            status = status_var.get()
            if status == "done":
                mark_value = 100
            elif status == "not_done":
                mark_value = 0
            else:
                try:
                    mark_value = int(partial_var.get())
                except ValueError:
                    messagebox.showerror("Ошибка", "Введите целое число от 1 до 99", parent=dialog)
                    return
                if not (1 <= mark_value <= 99):
                    messagebox.showerror("Ошибка", "Значение должно быть от 1 до 99", parent=dialog)
                    return

            try:
                self.marks_repo.add(
                    duty_id=self.selected_duty_id,
                    period_id=self.current_period_id,
                    marked_at=datetime_utils.get_now_iso(),
                    status=status,
                    mark_value=mark_value,
                    note=note_var.get().strip() or None,
                )
            except Exception as e:
                messagebox.showerror("Ошибка БД", f"Не удалось сохранить отметку:\n{e}", parent=dialog)
                return

            dialog.destroy()
            self._load_data()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=15)
        tk.Button(frame_btns, text="Отметить", command=apply, width=15).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=dialog.destroy, width=10).pack(side="left", padx=5)

    def _on_unmark(self):
        if not self.selected_duty_id or self.current_period_id is None:
            return
        if not messagebox.askyesno(
            "Подтверждение",
            "Снять все отметки о выполнении этой обязанности за период?\n"
            "Активности останутся."
        ):
            return
        try:
            self.marks_repo.delete_all_for_period(self.selected_duty_id, self.current_period_id)
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось снять отметку:\n{e}")
            return
        self._load_data()

    # ------------------------------------------------------------------
    # Добавить активность (с отметкой опционально)
    # ------------------------------------------------------------------
    def _open_add_activity_dialog(self):
        if not self.selected_duty_id or self.current_period_meta is None:
            return

        duty = next((d for d in self.duties if d["id"] == self.selected_duty_id), None)
        if not duty:
            return

        d_type_id = duty["activity_type_id"]
        d_role_id = duty["role_id"]
        d_sub_id = duty["sub_role_id"]

        fs_iso = self.current_period_meta[4]
        fe_iso = self.current_period_meta[5]

        # P-01.1: предупреждение, если есть ЛЮБАЯ отметка И хотя бы одна активность
        existing_mark = self.current_marks.get(self.selected_duty_id)
        existing_activities = self.activities_repo.get_by_duty_and_period(
            self.selected_duty_id, fs_iso, fe_iso
        )
        if existing_mark and existing_activities:
            mark_status = self._format_mark_status(existing_mark)
            if not messagebox.askyesno(
                "Обязанность уже отмечена",
                f"Обязанность «{duty['name']}» уже отмечена: {mark_status}.\n"
                f"Активностей за период уже: {len(existing_activities)}.\n\n"
                f"Точно добавить ещё одну активность?"
            ):
                return

        today_dt = datetime_utils.to_datetime(datetime_utils.get_now_iso())
        init_date = today_dt

        max_end = self.activities_repo.get_max_end_time()
        if max_end:
            dt_max = datetime_utils.to_datetime(max_end)
            init_start_h = dt_max.strftime("%H")
            init_start_m = dt_max.strftime("%M")
        else:
            init_start_h = "10"
            init_start_m = "00"

        init_end_h = today_dt.strftime("%H")
        init_end_m = today_dt.strftime("%M")

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Добавить активность к обязанности")
        dialog.grab_set()

        dialog.update_idletasks()
        dw, dh = 480, 700
        parent = self.winfo_toplevel()
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        dialog.geometry(f"{dw}x{dh}+{max(x, 0)}+{max(y, 0)}")

        # --- Дата ---
        tk.Label(dialog, text="Дата:", font=("Arial", 10, "bold")).pack(pady=(15, 0))
        cal = DateEntry(dialog, width=12, background='darkblue',
                        foreground='white', borderwidth=2,
                        year=init_date.year, month=init_date.month, day=init_date.day,
                        locale='ru_RU')
        cal.pack(pady=5)

        # --- Время начала ---
        tk.Label(dialog, text="Время начала:", font=("Arial", 10, "bold")).pack(pady=(10, 2))
        frame_start = tk.Frame(dialog)
        frame_start.pack()

        var_start_h = tk.StringVar(value=init_start_h)
        var_start_m = tk.StringVar(value=init_start_m)
        tk.Spinbox(frame_start, from_=0, to=23, width=3, textvariable=var_start_h,
                   format="%02.0f", font=("Arial", 11)).pack(side="left", padx=2)
        tk.Label(frame_start, text=":", font=("Arial", 11, "bold")).pack(side="left")
        tk.Spinbox(frame_start, from_=0, to=59, width=3, textvariable=var_start_m,
                   format="%02.0f", font=("Arial", 11)).pack(side="left", padx=2)

        # --- Время окончания ---
        tk.Label(dialog, text="Время окончания (можно оставить пустым):",
                 font=("Arial", 10, "bold")).pack(pady=(10, 2))
        frame_end = tk.Frame(dialog)
        frame_end.pack()

        var_end_h = tk.StringVar(value=init_end_h)
        var_end_m = tk.StringVar(value=init_end_m)
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

        # --- Заметки активности ---
        tk.Label(dialog, text="Заметки:").pack(anchor="w", padx=20, pady=(15, 2))
        notes_var = tk.StringVar()
        tk.Entry(dialog, textvariable=notes_var, width=50).pack(padx=20, pady=2)

        # --- Блок отметки ---
        frame_mark = tk.LabelFrame(dialog, text="Отметка о выполнении", padx=5, pady=5)
        frame_mark.pack(fill="x", padx=20, pady=(15, 5))

        # Чекбокс: отмечен, если отметки нет; снят, если есть
        var_mark = tk.BooleanVar(value=(existing_mark is None))
        chk_mark = tk.Checkbutton(
            frame_mark, text="Отметить выполнение",
            variable=var_mark, font=("Arial", 10, "bold")
        )
        chk_mark.pack(anchor="w")

        status_var = tk.StringVar(value="done")
        rb_done = tk.Radiobutton(frame_mark, text="✓ Выполнено полностью (100%)",
                                 variable=status_var, value="done")
        rb_done.pack(anchor="w", padx=20)
        rb_not_done = tk.Radiobutton(frame_mark, text="✗ Не выполнено (0%)",
                                     variable=status_var, value="not_done")
        rb_not_done.pack(anchor="w", padx=20)
        rb_partial = tk.Radiobutton(frame_mark, text="~ Выполнено частично:",
                                    variable=status_var, value="partial")
        rb_partial.pack(anchor="w", padx=20)

        frame_partial = tk.Frame(frame_mark)
        frame_partial.pack(fill="x", padx=40, pady=(0, 5))
        partial_var = tk.StringVar(value="50")
        entry_partial = tk.Entry(frame_partial, textvariable=partial_var, width=10, state="disabled")
        entry_partial.pack(side="left")
        tk.Label(frame_partial, text="% (1-99)").pack(side="left", padx=5)

        frame_mark_comment = tk.Frame(frame_mark)
        frame_mark_comment.pack(fill="x", padx=20, pady=(5, 0))
        tk.Label(frame_mark_comment, text="Комментарий:").pack(side="left")
        mark_note_var = tk.StringVar()
        tk.Entry(frame_mark_comment, textvariable=mark_note_var, width=30).pack(
            side="left", padx=5, fill="x", expand=True
        )

        def _update_mark_state():
            is_on = var_mark.get()
            st = "normal" if is_on else "disabled"
            for rb in (rb_done, rb_not_done, rb_partial):
                rb.config(state=st)
            if is_on and status_var.get() == "partial":
                entry_partial.config(state="normal")
            else:
                entry_partial.config(state="disabled")

        chk_mark.config(command=_update_mark_state)

        def _on_status_change():
            if var_mark.get() and status_var.get() == "partial":
                entry_partial.config(state="normal")
            else:
                entry_partial.config(state="disabled")

        for rb in (rb_done, rb_not_done, rb_partial):
            rb.config(command=_on_status_change)

        _update_mark_state()

        # --- Кнопки ---
        def apply():
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
                messagebox.showerror(
                    "Ошибка",
                    "Заполните оба поля времени окончания или оставьте оба пустыми",
                    parent=dialog
                )
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

            if not (fs_iso <= start_iso < fe_iso):
                messagebox.showerror(
                    "Ошибка",
                    f"Время начала должно попадать в выбранный период:\n"
                    f"{fs_iso} .. {fe_iso}\n"
                    f"(не включая правую границу)",
                    parent=dialog
                )
                return

            try:
                self.activities_repo.add(
                    type_id=d_type_id,
                    role_id=d_role_id,
                    sub_role_id=d_sub_id,
                    start_time=start_iso,
                    end_time=end_iso,
                    duration=None,
                    clean_duration=None,
                    breaks_duration=None,
                    engagement=None,
                    is_estimated=0,
                    source="manual",
                    notes=notes_var.get().strip(),
                    regular_duty_id=self.selected_duty_id,
                )
            except Exception as e:
                messagebox.showerror("Ошибка БД", f"Не удалось добавить активность:\n{e}", parent=dialog)
                return

            # Отметка (если отмечен чекбокс)
            if var_mark.get():
                status = status_var.get()
                if status == "done":
                    mark_value = 100
                elif status == "not_done":
                    mark_value = 0
                else:
                    try:
                        mark_value = int(partial_var.get())
                    except ValueError:
                        messagebox.showerror(
                            "Ошибка",
                            "Активность добавлена, но в отметке некорректный процент.\n"
                            "Отметьте выполнение отдельно через «Отметить выполнение».",
                            parent=dialog
                        )
                        dialog.destroy()
                        self._load_data()
                        return
                    if not (1 <= mark_value <= 99):
                        messagebox.showerror(
                            "Ошибка",
                            "Активность добавлена, но процент должен быть 1-99.\n"
                            "Отметьте выполнение отдельно.",
                            parent=dialog
                        )
                        dialog.destroy()
                        self._load_data()
                        return

                try:
                    self.marks_repo.add(
                        duty_id=self.selected_duty_id,
                        period_id=self.current_period_id,
                        marked_at=datetime_utils.get_now_iso(),
                        status=status,
                        mark_value=mark_value,
                        note=mark_note_var.get().strip() or None,
                    )
                except Exception as e:
                    messagebox.showerror(
                        "Ошибка отметки",
                        f"Активность добавлена, но отметку сохранить не удалось:\n{e}",
                        parent=dialog
                    )
                    dialog.destroy()
                    self._load_data()
                    return

            dialog.destroy()
            self._load_data()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=15)
        tk.Button(frame_btns, text="Создать", command=apply, width=15).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=dialog.destroy, width=10).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Редактирование активности (двойной клик по строке в sheet_activities)
    # ------------------------------------------------------------------
    def _on_activity_double_click(self, event):
        row = self.sheet_activities.identify_row(event)
        if row == "" or row is None:
            return
        try:
            row = int(row)
        except ValueError:
            return
        act_id = self.sheet_activities.get_cell_data(row, 0)
        try:
            act_id = int(act_id)
        except (ValueError, TypeError):
            return
        self._open_edit_activity_dialog(act_id)

    def _open_edit_activity_dialog(self, act_id):
        act = self.activities_repo.get_by_id(act_id)
        if not act:
            messagebox.showerror("Ошибка", f"Активность id={act_id} не найдена")
            return

        (_id, type_id, role_id, sub_role_id, start_iso, end_iso, duration,
         clean_duration, breaks_duration, engagement, is_estimated, source,
         notes, regular_duty_id) = act

        start_dt = datetime_utils.to_datetime(start_iso) if start_iso else None
        end_dt = datetime_utils.to_datetime(end_iso) if end_iso else None

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Редактировать активность")
        dialog.grab_set()

        dialog.update_idletasks()
        dw, dh = 440, 420
        parent = self.winfo_toplevel()
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 2
        dialog.geometry(f"{dw}x{dh}+{max(x, 0)}+{max(y, 0)}")

        # --- Дата ---
        tk.Label(dialog, text="Дата:", font=("Arial", 10, "bold")).pack(pady=(15, 0))
        if start_dt:
            init_year, init_month, init_day = start_dt.year, start_dt.month, start_dt.day
        else:
            now = datetime_utils.to_datetime(datetime_utils.get_now_iso())
            init_year, init_month, init_day = now.year, now.month, now.day
        cal = DateEntry(dialog, width=12, background='darkblue',
                        foreground='white', borderwidth=2,
                        year=init_year, month=init_month, day=init_day,
                        locale='ru_RU')
        cal.pack(pady=5)

        # --- Время начала ---
        tk.Label(dialog, text="Время начала:", font=("Arial", 10, "bold")).pack(pady=(10, 2))
        frame_start = tk.Frame(dialog)
        frame_start.pack()

        init_start_h = start_dt.strftime("%H") if start_dt else "10"
        init_start_m = start_dt.strftime("%M") if start_dt else "00"
        var_start_h = tk.StringVar(value=init_start_h)
        var_start_m = tk.StringVar(value=init_start_m)
        tk.Spinbox(frame_start, from_=0, to=23, width=3, textvariable=var_start_h,
                   format="%02.0f", font=("Arial", 11)).pack(side="left", padx=2)
        tk.Label(frame_start, text=":", font=("Arial", 11, "bold")).pack(side="left")
        tk.Spinbox(frame_start, from_=0, to=59, width=3, textvariable=var_start_m,
                   format="%02.0f", font=("Arial", 11)).pack(side="left", padx=2)

        # --- Время окончания ---
        tk.Label(dialog, text="Время окончания (можно оставить пустым):",
                 font=("Arial", 10, "bold")).pack(pady=(10, 2))
        frame_end = tk.Frame(dialog)
        frame_end.pack()

        init_end_h = end_dt.strftime("%H") if end_dt else ""
        init_end_m = end_dt.strftime("%M") if end_dt else ""
        var_end_h = tk.StringVar(value=init_end_h)
        var_end_m = tk.StringVar(value=init_end_m)
        tk.Spinbox(frame_end, from_=0, to=23, width=3, textvariable=var_end_h,
                   format="%02.0f", font=("Arial", 11)).pack(side="left", padx=2)
        tk.Label(frame_end, text=":", font=("Arial", 11, "bold")).pack(side="left")
        tk.Spinbox(frame_end, from_=0, to=59, width=3, textvariable=var_end_m,
                   format="%02.0f", font=("Arial", 11)).pack(side="left", padx=2)

        # --- Заметки ---
        tk.Label(dialog, text="Заметки:").pack(anchor="w", padx=20, pady=(15, 2))
        notes_var = tk.StringVar(value=notes or "")
        tk.Entry(dialog, textvariable=notes_var, width=50).pack(padx=20, pady=2)

        def apply():
            try:
                sh = int(var_start_h.get())
                sm = int(var_start_m.get())
            except (ValueError, TypeError):
                messagebox.showerror("Ошибка", "Некорректное время начала", parent=dialog)
                return
            if not (0 <= sh <= 23 and 0 <= sm <= 59):
                messagebox.showerror("Ошибка", "Часы 0-23, минуты 0-59", parent=dialog)
                return

            sd = cal.get_date()
            start_iso_new = f"{sd.year}-{sd.month:02d}-{sd.day:02d}T{sh:02d}:{sm:02d}:00+03:00"

            end_h_str = str(var_end_h.get()).strip()
            end_m_str = str(var_end_m.get()).strip()

            if end_h_str == "" and end_m_str == "":
                end_iso_new = None
                dur = 0
            elif end_h_str == "" or end_m_str == "":
                messagebox.showerror(
                    "Ошибка",
                    "Заполните оба поля времени окончания или оставьте оба пустыми",
                    parent=dialog
                )
                return
            else:
                try:
                    eh = int(end_h_str)
                    em = int(end_m_str)
                except (ValueError, TypeError):
                    messagebox.showerror("Ошибка", "Некорректное время окончания", parent=dialog)
                    return
                if not (0 <= eh <= 23 and 0 <= em <= 59):
                    messagebox.showerror("Ошибка", "Часы 0-23, минуты 0-59", parent=dialog)
                    return
                end_iso_new = f"{sd.year}-{sd.month:02d}-{sd.day:02d}T{eh:02d}:{em:02d}:00+03:00"
                if end_iso_new <= start_iso_new:
                    messagebox.showerror("Ошибка", "Конец должен быть позже начала", parent=dialog)
                    return
                sdt = datetime_utils.to_datetime(start_iso_new)
                edt = datetime_utils.to_datetime(end_iso_new)
                dur = int((edt - sdt).total_seconds() / 60)

            try:
                self.activities_repo.update(
                    act_id=act_id,
                    type_id=type_id,
                    role_id=role_id,
                    sub_role_id=sub_role_id,
                    start_time=start_iso_new,
                    end_time=end_iso_new,
                    duration=duration,
                    clean_duration=clean_duration,
                    breaks_duration=breaks_duration,
                    engagement=engagement,
                    is_estimated=is_estimated or 0,
                    source=source or "manual",
                    notes=notes_var.get().strip(),
                    regular_duty_id=regular_duty_id,
                )
            except Exception as e:
                messagebox.showerror("Ошибка БД", f"Не удалось сохранить:\n{e}", parent=dialog)
                return

            dialog.destroy()
            self._load_data()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=15)
        tk.Button(frame_btns, text="Сохранить", command=apply, width=15).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=dialog.destroy, width=10).pack(side="left", padx=5)