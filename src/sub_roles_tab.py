# src/sub_roles_tab.py
# Вкладка "Под-роли" с режимом Мастер-Деталь (Master-Detail).

import json
import tkinter as tk
from tkinter import ttk, messagebox
from tksheet import Sheet
from .sub_roles_repo import SubRolesRepository
from .roles_repo import RolesRepository
from .preferences_repo import PreferencesRepository


class SubRolesTab(tk.Frame):
    def __init__(self, parent, sub_roles_repo: SubRolesRepository, roles_repo: RolesRepository, prefs_repo: PreferencesRepository):
        super().__init__(parent)
        self.sub_roles_repo = sub_roles_repo
        self.roles_repo = roles_repo
        self.prefs_repo = prefs_repo

        self.current_parent_id = None
        self.sort_col = self.prefs_repo.get("sub_roles_sort_col")
        self.sort_asc = self.prefs_repo.get("sub_roles_sort_asc")
        self.tree_sort_col = self.prefs_repo.get("sub_roles_tree_sort_col")
        self.tree_sort_asc = self.prefs_repo.get("sub_roles_tree_sort_asc")

        # --- Верхняя панель с переключателем ---
        frame_top = tk.Frame(self)
        frame_top.pack(fill="x", padx=10, pady=5)

        tk.Label(frame_top, text="Расположение:").pack(side="left")

        self.layout_var = tk.StringVar(value=self.prefs_repo.get("sub_roles_layout"))
        tk.Radiobutton(frame_top, text="Слева-справа", variable=self.layout_var, value="left_right", command=self._on_layout_change).pack(side="left", padx=5)
        tk.Radiobutton(frame_top, text="Сверху-снизу", variable=self.layout_var, value="top_bottom", command=self._on_layout_change).pack(side="left", padx=5)

        # --- Основной контейнер ---
        self.paned = tk.PanedWindow(self, orient="horizontal", sashwidth=5, sashrelief="raised")
        self.paned.pack(fill="both", expand=True, padx=10, pady=5)

        # 1. Левая часть: Список ролей
        self.frame_roles = tk.Frame(self.paned)
        self.paned.add(self.frame_roles, stretch="always")

        tk.Label(self.frame_roles, text="Роли (выберите для просмотра):").pack(anchor="w")

        self.tree_roles = ttk.Treeview(self.frame_roles, columns=("id", "name"), show="headings", selectmode="browse")
        self.tree_roles.heading("id", text="ID", command=lambda c="#1": self.sort_tree_roles(c))
        self.tree_roles.heading("name", text="Название", command=lambda c="#2": self.sort_tree_roles(c))
        self.tree_roles.column("id", width=50, anchor="center")
        self.tree_roles.column("name", width=150)
        self.tree_roles.pack(fill="both", expand=True, pady=5)

        self.tree_roles.tag_configure("colored_role", font=("Arial", 10, "bold"))

        self.tree_roles.bind("<<TreeviewSelect>>", self._on_role_select)

        # 2. Правая часть: Таблица под-ролей
        self.frame_sub_roles = tk.Frame(self.paned)
        self.paned.add(self.frame_sub_roles, stretch="always")

        frame_buttons = tk.Frame(self.frame_sub_roles)
        frame_buttons.pack(pady=5, fill="x")

        self.btn_add = tk.Button(frame_buttons, text="Добавить под-роль", command=self.on_add_row, state="disabled")
        self.btn_add.pack(side="left", padx=5)

        self.btn_del = tk.Button(frame_buttons, text="Удалить выбранное", command=self.on_delete_row)
        self.btn_del.pack(side="left", padx=5)

        self.btn_refresh = tk.Button(frame_buttons, text="Обновить", command=self.refresh_all)
        self.btn_refresh.pack(side="left", padx=5)

        self.sheet = Sheet(
            self.frame_sub_roles,
            headers=["ID", "Название", "Описание"],
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
        self.sheet.pack(fill="both", expand=True)
        self.sheet.enable_bindings("all")
        self.sheet.readonly_columns(columns=[0])
        self.sheet.extra_bindings("end_edit_cell", self.on_cell_edited)
        self.sheet.extra_bindings("column_select", self.on_column_select)

        self._apply_layout()
        self.refresh_all()

    def _apply_layout(self):
        layout = self.layout_var.get()
        if layout == "top_bottom":
            self.paned.configure(orient="vertical")
        else:
            self.paned.configure(orient="horizontal")

    def _on_layout_change(self):
        self.prefs_repo.set("sub_roles_layout", self.layout_var.get())
        self._apply_layout()

    def refresh_all(self):
        self._load_roles_list()
        self.refresh_table()

    def sort_tree_roles(self, col):
        if self.tree_sort_col == col:
            self.tree_sort_asc = not self.tree_sort_asc
        else:
            self.tree_sort_col = col
            self.tree_sort_asc = True
        self._apply_tree_sort()
        self.prefs_repo.set("sub_roles_tree_sort_col", self.tree_sort_col)
        self.prefs_repo.set("sub_roles_tree_sort_asc", self.tree_sort_asc)

    def _apply_tree_sort(self):
        if self.tree_sort_col is None:
            return
        items = [(self.tree_roles.set(k, self.tree_sort_col), k) for k in self.tree_roles.get_children('')]
        if self.tree_sort_col == "#1":
            items.sort(key=lambda t: int(t[0]), reverse=not self.tree_sort_asc)
        else:
            items.sort(key=lambda t: t[0].lower(), reverse=not self.tree_sort_asc)
        for index, (val, k) in enumerate(items):
            self.tree_roles.move(k, '', index)
        arrow = " ▲" if self.tree_sort_asc else " ▼"
        self.tree_roles.heading("#1", text="ID" + (arrow if self.tree_sort_col == "#1" else ""))
        self.tree_roles.heading("#2", text="Название" + (arrow if self.tree_sort_col == "#2" else ""))

    def _load_roles_list(self):
        selected_item = self.tree_roles.selection()
        selected_id = None
        if selected_item:
            selected_id = self.tree_roles.item(selected_item[0], "values")[0]

        for item in self.tree_roles.get_children():
            self.tree_roles.delete(item)

        roles = self.roles_repo.get_all()
        for role in roles:
            role_id, name, color = role[0], role[1], role[3]
            color = color or "#FFFFFF"
            tag_color = f"tag_{role_id}"
            self.tree_roles.tag_configure(tag_color, background=color) # Применяем к фону
            self.tree_roles.insert("", "end", values=(role_id, name), tags=("colored_role", tag_color))

        self._apply_tree_sort()

        if selected_id:
            for item in self.tree_roles.get_children():
                if str(self.tree_roles.item(item, "values")[0]) == str(selected_id):
                    self.tree_roles.selection_set(item)
                    self.tree_roles.focus(item)
                    self.current_parent_id = selected_id
                    self.btn_add.config(state="normal")
                    break

        if not self.current_parent_id and roles:
            first_item = self.tree_roles.get_children()[0]
            self.tree_roles.selection_set(first_item)
            self.tree_roles.focus(first_item)
            self.current_parent_id = self.tree_roles.item(first_item, "values")[0]
            self.btn_add.config(state="normal")

        if not roles:
            self.btn_add.config(state="disabled")

    def _on_role_select(self, event):
        selected = self.tree_roles.selection()
        if not selected:
            return
        self.current_parent_id = self.tree_roles.item(selected[0], "values")[0]
        self.btn_add.config(state="normal")
        self.refresh_table()

    def refresh_table(self):
        if self.current_parent_id is None:
            self.sheet.set_sheet_data([])
            return
        sub_roles = self.sub_roles_repo.get_by_parent(self.current_parent_id)
        data = [list(sr) for sr in sub_roles]
        self.sheet.set_sheet_data(data, reset_col_positions=False)
        if self.sort_col is not None:
            self.sheet.sort_rows_by_column(column=self.sort_col, reverse=not self.sort_asc)
        self._load_sheet_state()

    def save_state(self):
        widths = self.sheet.get_column_widths()
        self.prefs_repo.set("sub_roles_col_widths", json.dumps(widths))
        self.prefs_repo.set("sub_roles_sort_col", self.sort_col)
        self.prefs_repo.set("sub_roles_sort_asc", self.sort_asc)

    def _load_sheet_state(self):
        try:
            widths = json.loads(self.prefs_repo.get("sub_roles_col_widths"))
            if isinstance(widths, list) and len(widths) == 3 and all(w is not None for w in widths):
                self.sheet.set_column_widths([int(w) for w in widths])
            else:
                raise ValueError()
        except Exception:
            self.sheet.set_column_widths([50, 200, 300])

    def on_cell_edited(self, event):
        row = getattr(event.selected, "row", None)
        col = getattr(event.selected, "column", None)
        if row is None or col is None:
            return
        sub_role_id = self.sheet.get_cell_data(row, 0)
        if sub_role_id is None:
            return
        name = self.sheet.get_cell_data(row, 1)
        desc = self.sheet.get_cell_data(row, 2)
        if col == 1 and (name is None or str(name).strip() == ""):
            messagebox.showwarning("Ошибка", "Название под-роли не может быть пустым!")
            self.refresh_table()
            return
        try:
            self.sub_roles_repo.update(sub_role_id, name, desc)
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
        if self.current_parent_id is None:
            return
        try:
            self.sub_roles_repo.add("Новая под-роль", "", self.current_parent_id)
            self.refresh_table()
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось добавить под-роль:\n{e}")

    def on_delete_row(self):
        selected = self.sheet.get_currently_selected()
        row = getattr(selected, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите под-роль для удаления!")
            return
        sub_role_id = self.sheet.get_cell_data(row, 0)
        if sub_role_id is None:
            return
        if messagebox.askyesno("Подтверждение", "Удалить выбранную под-роль?"):
            try:
                self.sub_roles_repo.delete(sub_role_id)
                self.refresh_table()
            except Exception as e:
                messagebox.showerror("Ошибка БД", f"Не удалось удалить под-роль:\n{e}")