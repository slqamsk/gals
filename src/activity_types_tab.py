# src/activity_types_tab.py
# Вкладка для управления справочником типов активностей.

import json
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from tksheet import Sheet
from .activity_types_repo import ActivityTypesRepository
from .roles_repo import RolesRepository
from .sub_roles_repo import SubRolesRepository
from .preferences_repo import PreferencesRepository


class ActivityTypesTab(tk.Frame):
    # Инициализирует вкладку и элементы интерфейса.
    def __init__(self, parent, types_repo: ActivityTypesRepository, roles_repo: RolesRepository,
                 sub_roles_repo: SubRolesRepository, prefs_repo: PreferencesRepository):
        super().__init__(parent)
        self.types_repo = types_repo
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.prefs_repo = prefs_repo
        self.sort_col = None
        self.sort_asc = True

        self.roles_map = {}
        self.sub_roles_map = {}

        # --- Панель кнопок ---
        frame_buttons = tk.Frame(self)
        frame_buttons.pack(pady=5, padx=10, fill="x")

        self.btn_add = tk.Button(frame_buttons, text="Добавить тип", command=self.on_add_row)
        self.btn_add.pack(side="left", padx=5)

        self.btn_del = tk.Button(frame_buttons, text="Удалить выбранное", command=self.on_delete_row)
        self.btn_del.pack(side="left", padx=5)

        self.btn_refresh = tk.Button(frame_buttons, text="Обновить", command=self.refresh_table)
        self.btn_refresh.pack(side="left", padx=5)

        lbl_hint = tk.Label(frame_buttons, text="(Двойной клик по 'Роль' или 'Под-роль' откроет иерархию)", fg="gray")
        lbl_hint.pack(side="right", padx=5)

        # --- Таблица tksheet ---
        self.sheet = Sheet(
            self,
            headers=["ID", "Название", "Описание", "Роль (по умолч.)", "Под-роль (по умолч.)", "Частота (1-10)",
                     "Важность (1-10)"],
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

        # 1. Делаем колонки ID (0), Роль (3) и Под-роль (4) недоступными для стандартного редактирования
        self.sheet.readonly_columns(columns=[0, 3, 4])

        # 2. Привязываем двойной клик к ВНУТРЕННЕМУ холсту таблицы (MT), а не к самому фрейму.
        # Параметр add="+" позволяет сработать нашему обработчику вместе со встроенным.
        self.sheet.MT.bind("<Double-Button-1>", self.on_double_click, add="+")  # <--- КЛЮЧЕВАЯ СТРОКА 1

        self.sheet.extra_bindings("end_edit_cell", self.on_cell_edited)
        self.sheet.extra_bindings("column_select", self.on_column_select)

        self.refresh_table()
        self._load_state()

    # 3. Обработчик двойного клика (вычисляем координаты и открываем окно)
    def on_double_click(self, event):  # <--- КЛЮЧЕВОЙ МЕТОД
        # event.y и event.x здесь относятся к внутреннему холсту (MT)
        row = self.sheet.identify_row(event)
        col = self.sheet.identify_column(event)

        # Если кликнули вне ячеек
        if row == "" or col == "":
            return

        try:
            row = int(row)
            col = int(col)
        except ValueError:
            return

        # Если кликнули по колонке Роль (3) или Под-роль (4)
        if col == 3 or col == 4:
            self._open_hierarchy_picker(row)

    # Открывает окно выбора роли/подроли.
    def _open_hierarchy_picker(self, row):
        picker = tk.Toplevel(self)
        picker.transient(self.winfo_toplevel())
        picker.title("Выбор роли и под-роли")

        picker.update_idletasks()
        screen_width = picker.winfo_screenwidth()
        pos_x = (screen_width - 400) // 2
        picker.geometry(f"400x500+{pos_x}+50")
        picker.grab_set()

        # Дерево ролей
        tree = ttk.Treeview(picker, columns=("type", "id"), selectmode="browse")
        tree.heading("#0", text="Роль / Под-роль")
        tree.column("#0", width=350)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        # Заполняем дерево (сортируем по ID)
        roles = sorted(self.roles_repo.get_all(), key=lambda r: r[0])
        for r in roles:
            role_text = f"{r[0]}. {r[1]}"
            r_node = tree.insert("", "end", text=role_text, values=("role", r[0]))

            sub_roles = sorted(self.sub_roles_repo.get_by_parent(r[0]), key=lambda sr: sr[0])
            for sr in sub_roles:
                tree.insert(r_node, "end", text=sr[1], values=("sub_role", sr[0]), tags=(f"parent_{r[0]}",))

        # Панель кнопок
        frame_btns = tk.Frame(picker)
        frame_btns.pack(fill="x", pady=10, padx=10)

        def clear_role():
            self.sheet.set_cell_data(row, 3, "")
            self._save_row(row)
            tree.selection_remove(tree.selection())

        def clear_sub_role():
            self.sheet.set_cell_data(row, 4, "")
            self._save_row(row)
            tree.selection_remove(tree.selection())

        tk.Button(frame_btns, text="Очистить роль", command=clear_role, fg="red").pack(side="left", padx=5)
        tk.Button(frame_btns, text="Очистить под-роль", command=clear_sub_role, fg="red").pack(side="left", padx=5)

        # Логика выбора
        def select_item(event=None):
            selected = tree.selection()
            if not selected:
                return
            item = tree.item(selected[0])
            val_type = item["values"][0]
            val_id = item["values"][1]

            current_role_name = self.sheet.get_cell_data(row, 3)
            current_sub_name = self.sheet.get_cell_data(row, 4)

            if val_type == "role":
                if current_sub_name:
                    current_sub_id = self.sub_roles_map.get(current_sub_name)
                    if current_sub_id:
                        conn = self.sub_roles_repo.db.connect()
                        parent_id = \
                        conn.execute("SELECT parent_role_id FROM sub_roles WHERE id=?", (current_sub_id,)).fetchone()[0]
                        conn.close()
                        if str(parent_id) != str(val_id):
                            messagebox.showerror("Ошибка",
                                                 "Сначала очистите под-роль, так как она принадлежит другой роли.")
                            return

                role_name = item["text"].split(". ", 1)[1]
                self.sheet.set_cell_data(row, 3, role_name)

            else:
                if current_role_name:
                    current_role_id = self.roles_map.get(current_role_name)
                    parent_role_id = item["tags"][0].replace("parent_", "")
                    if current_role_id and str(current_role_id) != str(parent_role_id):
                        messagebox.showerror("Ошибка",
                                             "Сначала очистите роль, так как она не соответствует родителю этой под-роли.")
                        return

                self.sheet.set_cell_data(row, 4, item["text"])

                parent_role_id = item["tags"][0].replace("parent_", "")
                for r in self.roles_repo.get_all():
                    if str(r[0]) == str(parent_role_id):
                        self.sheet.set_cell_data(row, 3, r[1])
                        break

            self._save_row(row)
            picker.destroy()

        tree.bind("<Double-Button-1>", select_item)
        tk.Button(frame_btns, text="Выбрать", command=select_item).pack(side="right", padx=5)

    def _load_state(self):
        try:
            widths = json.loads(self.prefs_repo.get("activity_types_col_widths"))
            if isinstance(widths, list) and len(widths) == 7 and all(w is not None for w in widths):
                self.sheet.set_column_widths([int(w) for w in widths])
            else:
                raise ValueError()
        except Exception:
            self.sheet.set_column_widths([50, 150, 200, 150, 150, 80, 80])

    def save_state(self):
        widths = self.sheet.get_column_widths()
        self.prefs_repo.set("activity_types_col_widths", json.dumps(widths))

    def refresh_table(self):
        self.roles_map = {r[1]: r[0] for r in self.roles_repo.get_all()}
        self.sub_roles_map = {}
        for r in self.roles_repo.get_all():
            for sr in self.sub_roles_repo.get_by_parent(r[0]):
                self.sub_roles_map[sr[1]] = sr[0]

        roles_id_to_name = {v: k for k, v in self.roles_map.items()}
        sub_roles_id_to_name = {v: k for k, v in self.sub_roles_map.items()}

        types = self.types_repo.get_all()
        data = []
        for t in types:
            t_id, name, desc, def_role_id, def_sub_id, freq, imp = t
            role_name = roles_id_to_name.get(def_role_id, "")
            sub_role_name = sub_roles_id_to_name.get(def_sub_id, "")
            data.append([t_id, name, desc or "", role_name, sub_role_name, freq, imp])

        self.sheet.set_sheet_data(data, reset_col_positions=False)

        if self.sort_col is not None:
            self.sheet.sort_rows_by_column(column=self.sort_col, reverse=not self.sort_asc)

    def _save_row(self, row):
        type_id = self.sheet.get_cell_data(row, 0)
        name = self.sheet.get_cell_data(row, 1)
        desc = self.sheet.get_cell_data(row, 2)
        role_name = self.sheet.get_cell_data(row, 3)
        sub_role_name = self.sheet.get_cell_data(row, 4)

        try:
            freq = int(float(self.sheet.get_cell_data(row, 5) or 1))
        except ValueError:
            freq = 1
            self.sheet.set_cell_data(row, 5, freq)

        try:
            imp = int(float(self.sheet.get_cell_data(row, 6) or 1))
        except ValueError:
            imp = 1
            self.sheet.set_cell_data(row, 6, imp)

        def_role_id = self.roles_map.get(role_name) if role_name else None
        def_sub_id = self.sub_roles_map.get(sub_role_name) if sub_role_name else None

        try:
            self.types_repo.update(type_id, name, desc, def_role_id, def_sub_id, freq, imp)
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка", "Тип активности с таким названием уже существует!")
            self.refresh_table()
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось сохранить изменение:\n{e}")
            self.refresh_table()

    def on_cell_edited(self, event):
        row = event.row
        col = event.column
        # Игнорируем колонки 0, 3, 4 (они readonly или сохраняются через окно выбора)
        if col in [0, 3, 4]:
            return

        name = self.sheet.get_cell_data(row, 1)
        if not name or not str(name).strip():
            messagebox.showwarning("Ошибка", "Название типа активности не может быть пустым!")
            self.refresh_table()
            return

        self._save_row(row)

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

    def on_add_row(self):
        try:
            self.types_repo.add("Новый тип", "", None, None, 1, 1)
            self.refresh_table()
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось добавить тип:\n{e}")

    def on_delete_row(self):
        selected = self.sheet.get_currently_selected()
        row = getattr(selected, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите тип активности для удаления!")
            return
        type_id = self.sheet.get_cell_data(row, 0)

        if messagebox.askyesno("Подтверждение", "Удалить выбранный тип активности?"):
            try:
                self.types_repo.delete(type_id)
                self.refresh_table()
            except sqlite3.IntegrityError:
                messagebox.showerror("Ошибка",
                                     "Нельзя удалить этот тип, так как он используется в активе (истории).")
            except Exception as e:
                messagebox.showerror("Ошибка БД", f"Не удалось удалить тип:\n{e}")