# src/measurements_history_tab.py
# Вкладка «История»: таблица всех сеансов измерений.
#
# Сортировка колонки «Дата-время» идёт по исходному ISO, а не по
# отображаемой строке «ДД.ММ.ГГГГ ЧЧ:ММ» (иначе 01.12 оказывался раньше 02.11).
import json
import tkinter as tk
from tkinter import ttk, messagebox

from tksheet import Sheet

from . import datetime_utils
from .ui_utils import sort_sheet_data


class MeasurementsHistoryTab(tk.Frame):
    WIDTHS = [50, 140, 120, 400, 200]

    def __init__(self, parent, repo, prefs_repo):
        super().__init__(parent)
        self.repo = repo
        self.prefs_repo = prefs_repo
        self.types_map = {}
        self.session_data = []

        self.sort_col = self.prefs_repo.get("measurements_history_sort_col")
        if self.sort_col is None:
            self.sort_col = 1
        self.sort_asc = self.prefs_repo.get("measurements_history_sort_asc")
        if self.sort_asc is None:
            self.sort_asc = False

        self._build_ui()
        self._load_state()
        self.refresh_table()

    def _build_ui(self):
        frame_top = tk.Frame(self)
        frame_top.pack(fill="x", padx=10, pady=5)

        tk.Label(frame_top, text="Тип:").pack(side="left")
        self.cb_filter = ttk.Combobox(frame_top, state="readonly", width=30)
        self.cb_filter.pack(side="left", padx=5)
        self.cb_filter.bind("<<ComboboxSelected>>", self._on_filter_changed)

        tk.Button(frame_top, text="Обновить",
                  command=self.refresh_table).pack(side="left", padx=5)
        tk.Button(frame_top, text="Удалить выбранный",
                  command=self._on_delete, fg="red").pack(side="left", padx=5)
        tk.Label(frame_top, text="(Двойной клик — подробности)",
                 fg="gray").pack(side="right", padx=5)

        self.sheet = Sheet(
            self,
            headers=["ID", "Дата-время", "Тип", "Значения", "Заметки"],
            show_row_index=False, show_top_left=False,
            show_x_scrollbar=True, show_y_scrollbar=True,
            table_grid_fg="#000000", outline_thickness=1,
            header_bg="#f0f0f0", header_fg="#000000",
            font=("Arial", 10, "normal"), header_font=("Arial", 10, "bold"),
            row_height=25, table_wrap="w", auto_resize_row_heights=True,
        )
        self.sheet.pack(fill="both", expand=True, padx=10, pady=5)
        self.sheet.enable_bindings("all")
        self.sheet.readonly_columns(columns=[0, 1, 2, 3, 4])
        self.sheet.MT.bind("<Double-Button-1>", self._on_double_click, add="+")
        self.sheet.extra_bindings("column_select", self._on_column_select)

    def _load_state(self):
        try:
            widths = json.loads(self.prefs_repo.get("measurements_history_col_widths"))
            if isinstance(widths, list) and len(widths) == 5:
                self.sheet.set_column_widths([int(w) for w in widths])
            else:
                raise ValueError()
        except Exception:
            self.sheet.set_column_widths(list(self.WIDTHS))

    def save_state(self):
        try:
            widths = self.sheet.get_column_widths()
            self.prefs_repo.set("measurements_history_col_widths", json.dumps(widths))
        except Exception:
            pass
        self.prefs_repo.set("measurements_history_sort_col", self.sort_col)
        self.prefs_repo.set("measurements_history_sort_asc", self.sort_asc)

    def refresh_all(self):
        self.refresh_table()

    def refresh_table(self):
        types = self.repo.get_all_types()
        self.types_map = {"Все": None}
        for t in types:
            self.types_map[t[1]] = t[0]

        prev = self.cb_filter.get() or "Все"
        self.cb_filter['values'] = list(self.types_map.keys())
        if prev in self.types_map:
            self.cb_filter.set(prev)
        else:
            self.cb_filter.set("Все")

        filter_type_id = self.types_map.get(self.cb_filter.get())
        try:
            self.session_data = self.repo.get_sessions_for_display(type_id=filter_type_id)
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось загрузить историю:\n{e}")
            self.session_data = []

        rows = []
        iso_by_id = {}
        for s in self.session_data:
            iso_by_id[s["id"]] = s["measured_at"] or ""
            dt = datetime_utils.to_display(s["measured_at"])
            values_str = " / ".join(
                f"{self._fmt_num(v['value'])} {v['unit']}"
                for v in s["values"]
            )
            rows.append([s["id"], dt, s["type_name"], values_str, s["notes"] or ""])

        if self.sort_col is not None:
            if self.sort_col == 1:
                # «Дата-время»: сортируем по исходному ISO.
                # Пустые значения — всегда в конце.
                valid = [r for r in rows if iso_by_id.get(r[0])]
                empty = [r for r in rows if not iso_by_id.get(r[0])]
                valid.sort(key=lambda r: iso_by_id[r[0]], reverse=not self.sort_asc)
                rows = valid + empty
            else:
                numeric_cols = [0] if self.sort_col == 0 else []
                rows = sort_sheet_data(rows, self.sort_col, self.sort_asc,
                                       numeric_cols=numeric_cols)

        self.sheet.set_sheet_data(rows, reset_col_positions=False)

    def _fmt_num(self, v):
        if v is None:
            return "—"
        try:
            f = float(v)
        except (ValueError, TypeError):
            return str(v)
        if f.is_integer():
            return str(int(f))
        return f"{f:g}"

    def _on_filter_changed(self, event=None):
        self.refresh_table()

    def _on_column_select(self, event):
        col = getattr(event.selected, "column", None)
        if col is None:
            return
        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True
        self.save_state()
        self.refresh_table()

    def _on_double_click(self, event):
        row = self.sheet.identify_row(event)
        if row == "" or row is None:
            return
        try:
            row = int(row)
        except ValueError:
            return
        session_id = self.sheet.get_cell_data(row, 0)
        try:
            session_id = int(session_id)
        except (ValueError, TypeError):
            return
        self._open_details_dialog(session_id)

    def _open_details_dialog(self, session_id):
        data = next((s for s in self.session_data if s["id"] == session_id), None)
        if not data:
            return

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title(f"Сеанс #{data['id']} — {data['type_name']}")
        dialog.geometry("500x400")
        dialog.grab_set()

        frame = tk.Frame(dialog, padx=15, pady=15)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Тип:", font=("Arial", 10, "bold"),
                 anchor="w").grid(row=0, column=0, sticky="w", pady=2)
        tk.Label(frame, text=data["type_name"],
                 anchor="w").grid(row=0, column=1, sticky="w", pady=2, padx=10)

        tk.Label(frame, text="Дата-время:", font=("Arial", 10, "bold"),
                 anchor="w").grid(row=1, column=0, sticky="w", pady=2)
        tk.Label(frame, text=datetime_utils.to_display(data["measured_at"]),
                 anchor="w").grid(row=1, column=1, sticky="w", pady=2, padx=10)

        tk.Label(frame, text="Значения:", font=("Arial", 10, "bold"),
                 anchor="w").grid(row=2, column=0, sticky="nw", pady=(10, 2))
        frame_vals = tk.Frame(frame)
        frame_vals.grid(row=2, column=1, sticky="w", pady=(10, 2), padx=10)
        for v in data["values"]:
            tk.Label(
                frame_vals,
                text=f"  {v['component_name']}: {self._fmt_num(v['value'])} {v['unit']}",
                anchor="w"
            ).pack(fill="x")

        tk.Label(frame, text="Заметки:", font=("Arial", 10, "bold"),
                 anchor="w").grid(row=3, column=0, sticky="nw", pady=(10, 2))
        tk.Label(frame, text=data["notes"] or "—", anchor="w",
                 wraplength=350, justify="left").grid(
            row=3, column=1, sticky="w", pady=(10, 2), padx=10)

        tk.Button(dialog, text="Закрыть", command=dialog.destroy, width=15).pack(pady=15)

    def _on_delete(self):
        sel = self.sheet.get_currently_selected()
        row = getattr(sel, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите сеанс для удаления")
            return
        session_id = self.sheet.get_cell_data(row, 0)
        try:
            session_id = int(session_id)
        except (ValueError, TypeError):
            return

        data = next((s for s in self.session_data if s["id"] == session_id), None)
        if not data:
            return

        if not messagebox.askyesno(
            "Подтверждение",
            f"Удалить сеанс #{session_id} ({data['type_name']}, "
            f"{datetime_utils.to_display(data['measured_at'])}?\n"
            f"Значения удалятся каскадно."
        ):
            return

        try:
            self.repo.delete_session(session_id)
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось удалить:\n{e}")
            return
        self.refresh_table()