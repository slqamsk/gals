# src/roles_excel_tab.py
# Вкладка "Роли": редактируемая таблица на основе tksheet с переносом текста.

import json
import sqlite3
import tkinter as tk
from tkinter import messagebox, colorchooser
from tksheet import Sheet
from .roles_repo import RolesRepository
from .preferences_repo import PreferencesRepository


# Вкладка с редактируемой таблицей ролей.
class RolesExcelTab(tk.Frame):
    def __init__(self, parent, roles_repo: RolesRepository, prefs_repo: PreferencesRepository):
        super().__init__(parent)
        self.roles_repo = roles_repo
        self.prefs_repo = prefs_repo
        self.sort_col = None
        self.sort_asc = True

        # --- Панель кнопок ---
        frame_buttons = tk.Frame(self)
        frame_buttons.pack(pady=5, padx=10, fill="x")

        self.btn_add = tk.Button(frame_buttons, text="Добавить строку", command=self.on_add_row)
        self.btn_add.pack(side="left", padx=5)

        self.btn_del = tk.Button(frame_buttons, text="Удалить выбранное", command=self.on_delete_row)
        self.btn_del.pack(side="left", padx=5)

        self.btn_refresh = tk.Button(frame_buttons, text="Обновить", command=self.refresh_table)
        self.btn_refresh.pack(side="left", padx=5)

        self.btn_color = tk.Button(frame_buttons, text="Выбрать цвет", command=self.on_pick_color)
        self.btn_color.pack(side="left", padx=5)

        lbl_hint = tk.Label(frame_buttons, text="(Двойной клик для редактирования текста или HEX-кода цвета)",
                            fg="gray")
        lbl_hint.pack(side="right", padx=5)

        # --- Таблица tksheet ---
        self.sheet = Sheet(
            self,
            headers=["ID", "Название", "Описание", "Цвет фона"],
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
        self.sheet.pack(fill="both", expand=True, padx=10, pady=10)

        self.sheet.enable_bindings("all")
        # Запрещаем редактировать только ID (колонка 0). Колонка 3 (Цвет) теперь доступна для ввода!
        self.sheet.readonly_columns(columns=[0])

        self.sheet.extra_bindings("end_edit_cell", self.on_cell_edited)
        self.sheet.extra_bindings("column_select", self.on_column_select)

        self.refresh_table()
        self._load_state()

    # Обработчик кнопки "Выбрать цвет".
    def on_pick_color(self):
        selected = self.sheet.get_currently_selected()
        row = getattr(selected, "row", None)

        if row is None:
            messagebox.showwarning("Внимание", "Сначала выберите роль в таблице!")
            return

        role_id = self.sheet.get_cell_data(row, 0)
        current_color = self.sheet.get_cell_data(row, 3) or "#FFFFFF"

        color_code = colorchooser.askcolor(initialcolor=current_color, title="Выберите цвет фона роли")

        if color_code[1]:
            new_color = color_code[1]
            name = self.sheet.get_cell_data(row, 1)
            desc = self.sheet.get_cell_data(row, 2)

            try:
                self.roles_repo.update(role_id, name, desc, new_color)
                self.sheet.set_cell_data(row, 3, new_color)
            except Exception as e:
                messagebox.showerror("Ошибка БД", f"Не удалось сохранить цвет:\n{e}")

    def _load_state(self):
        self.sort_col = self.prefs_repo.get("roles_sort_col")
        self.sort_asc = self.prefs_repo.get("roles_sort_asc")
        if self.sort_col is not None:
            self.sheet.sort_rows_by_column(column=self.sort_col, reverse=not self.sort_asc)

        try:
            widths = json.loads(self.prefs_repo.get("roles_col_widths"))
            if isinstance(widths, list) and len(widths) == 4 and all(w is not None for w in widths):
                self.sheet.set_column_widths([int(w) for w in widths])
            else:
                raise ValueError()
        except Exception:
            self.sheet.set_column_widths([50, 200, 300, 100])

    def save_state(self):
        widths = self.sheet.get_column_widths()
        self.prefs_repo.set("roles_col_widths", json.dumps(widths))
        self.prefs_repo.set("roles_sort_col", self.sort_col)
        self.prefs_repo.set("roles_sort_asc", self.sort_asc)

    def refresh_table(self):
        roles = self.roles_repo.get_all()
        data = [list(role) for role in roles]
        self.sheet.set_sheet_data(data, reset_col_positions=False)

        if self.sort_col is not None:
            self.sheet.sort_rows_by_column(column=self.sort_col, reverse=not self.sort_asc)

    def on_cell_edited(self, event):
        row = getattr(event.selected, "row", None)
        col = getattr(event.selected, "column", None)
        if row is None or col is None:
            return

        role_id = self.sheet.get_cell_data(row, 0)
        name = self.sheet.get_cell_data(row, 1)
        desc = self.sheet.get_cell_data(row, 2)
        color = self.sheet.get_cell_data(row, 3) or "#FFFFFF"

        # Валидация названия
        if col == 1 and (name is None or str(name).strip() == ""):
            messagebox.showwarning("Ошибка", "Название роли не может быть пустым!")
            self.refresh_table()
            return

        # Валидация цвета
        if col == 3:
            color_str = str(color).strip()
            if len(color_str) != 7 or not color_str.startswith('#'):
                messagebox.showwarning("Ошибка",
                                       "Неверный формат цвета.\nИспользуйте HEX-код (например, #FF0000 или #FFFFFF).")
                self.refresh_table()
                return
            color = color_str  # сохраняем очищенный от пробелов код

        try:
            self.roles_repo.update(role_id, name, desc, color)
            self.sheet.set_cell_data(row, 3, color)
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось сохранить изменение:\n{e}")
            self.refresh_table()

    def on_column_select(self, event):
        col = getattr(event.selected, "column", None)
        if col is None:
            return
        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True
        self.sheet.sort_rows_by_column(column=col, reverse=not self.sort_asc)
        self.save_state()

    def on_add_row(self):
        try:
            self.roles_repo.add("Новая роль", "", "#FFFFFF")
            self.refresh_table()
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось добавить роль:\n{e}")

    def on_delete_row(self):
        selected = self.sheet.get_currently_selected()
        row = getattr(selected, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите роль для удаления!")
            return
        role_id = self.sheet.get_cell_data(row, 0)
        if role_id is None:
            return
        if messagebox.askyesno("Подтверждение", "Удалить выбранную роль?"):
            try:
                self.roles_repo.delete(role_id)
                self.refresh_table()
            except sqlite3.IntegrityError:
                messagebox.showerror("Ошибка удаления",
                                     "Нельзя удалить эту роль, так как у неё есть под-роли.\nСначала удалите все под-роли.")
            except Exception as e:
                messagebox.showerror("Ошибка БД", f"Не удалось удалить роль:\n{e}")