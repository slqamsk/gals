# src/regular_duties_tab.py
# Вкладка для управления справочником регулярных обязанностей.

import json
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from tksheet import Sheet
from .regular_duties_repo import RegularDutiesRepository
from .activity_types_repo import ActivityTypesRepository
from .roles_repo import RolesRepository
from .sub_roles_repo import SubRolesRepository
from .preferences_repo import PreferencesRepository
from .ui_utils import sort_sheet_data


class RegularDutiesTab(tk.Frame):
    # Инициализирует вкладку и элементы интерфейса.
    def __init__(self, parent, duties_repo: RegularDutiesRepository,
                 types_repo: ActivityTypesRepository,
                 roles_repo: RolesRepository,
                 sub_roles_repo: SubRolesRepository,
                 prefs_repo: PreferencesRepository):
        super().__init__(parent)
        self.duties_repo = duties_repo
        self.types_repo = types_repo
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.prefs_repo = prefs_repo
        
        self.sort_col = self.prefs_repo.get("regular_duties_sort_col")
        if self.sort_col is None: self.sort_col = 0
        self.sort_asc = self.prefs_repo.get("regular_duties_sort_asc")
        if self.sort_asc is None: self.sort_asc = True

        self.roles_map = {}
        self.sub_roles_map = {}
        self.types_map = {}
        self.types_id_to_name = {}

        # --- Панель кнопок ---
        frame_buttons = tk.Frame(self)
        frame_buttons.pack(pady=5, padx=10, fill="x")

        self.btn_add = tk.Button(frame_buttons, text="Добавить обязанность", command=self.on_add_row)
        self.btn_add.pack(side="left", padx=5)

        self.btn_del = tk.Button(frame_buttons, text="Удалить выбранное", command=self.on_delete_row)
        self.btn_del.pack(side="left", padx=5)

        self.btn_refresh = tk.Button(frame_buttons, text="Обновить", command=self.refresh_table)
        self.btn_refresh.pack(side="left", padx=5)

        lbl_hint = tk.Label(
            frame_buttons,
            text="(Двойной клик по 'Тип', 'Период', 'Роль' или 'Под-роль' откроет выбор)",
            fg="gray"
        )
        lbl_hint.pack(side="right", padx=5)

        # --- Таблица tksheet ---
        self.sheet = Sheet(
            self,
            headers=["Порядок", "Название", "Описание", "Тип активности", "Период", "Роль", "Под-роль", "Важность", "ID"],
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

        # readonly: Тип (3), Период (4), Роль (5), Под-роль (6), ID (8)
        self.sheet.readonly_columns(columns=[3, 4, 5, 6, 8])

        self.sheet.MT.bind("<Double-Button-1>", self.on_double_click, add="+")

        self.sheet.extra_bindings("end_edit_cell", self.on_cell_edited)
        self.sheet.extra_bindings("column_select", self.on_column_select)

        self.refresh_table()
        self._load_state()

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

        if col == 3:
            self._open_type_picker(row)
        elif col == 4:
            self._open_period_picker(row)
        elif col == 5 or col == 6:
            self._open_role_picker(row)

    def _open_type_picker(self, row):
        picker = tk.Toplevel(self)
        picker.transient(self.winfo_toplevel())
        picker.title("Выбор типа активности")

        picker.update_idletasks()
        screen_width = picker.winfo_screenwidth()
        pos_x = (screen_width - 300) // 2
        picker.geometry(f"500x400+{pos_x}+100")
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

            self.sheet.set_cell_data(row, 3, type_name)

            # Если роль/подроль ещё не выбраны — подставляем дефолтные из типа
            t_data = next((t for t in types if t[0] == type_id), None)
            if t_data:
                current_role = self.sheet.get_cell_data(row, 5) or ""
                current_sub = self.sheet.get_cell_data(row, 6) or ""
                if not current_role:
                    def_role_id = t_data[3]
                    if def_role_id:
                        self.sheet.set_cell_data(row, 5, self.roles_id_to_name.get(def_role_id, ""))
                if not current_sub:
                    def_sub_id = t_data[4]
                    if def_sub_id:
                        self.sheet.set_cell_data(row, 6, self.sub_roles_id_to_name.get(def_sub_id, ""))

            self._save_row(row)
            picker.destroy()

        tree.bind("<Double-Button-1>", select)
        tk.Button(picker, text="Выбрать", command=select).pack(pady=10)

    def _open_period_picker(self, row):
        picker = tk.Toplevel(self)
        picker.transient(self.winfo_toplevel())
        picker.title("Выбор периода")
        picker.geometry("300x300+1200+200")
        picker.grab_set()

        current = self.sheet.get_cell_data(row, 4) or "week"
        var = tk.StringVar(value=current)

        tk.Label(picker, text="За какой период должна выполняться обязанность:",
                 font=("Arial", 10, "bold"), wraplength=230).pack(pady=10)

        for value, label in (("day", "День"), ("week", "Неделя"), ("month", "Месяц")):
            tk.Radiobutton(picker, text=label, variable=var, value=value).pack(anchor="w", padx=30)

        def apply():
            self.sheet.set_cell_data(row, 4, var.get())
            self._save_row(row)
            picker.destroy()

        tk.Button(picker, text="Применить", command=apply).pack(pady=15)

    def _open_role_picker(self, row):
        picker = tk.Toplevel(self)
        picker.transient(self.winfo_toplevel())
        picker.title("Выбор роли и под-роли")

        picker.update_idletasks()
        screen_width = picker.winfo_screenwidth()
        pos_x = (screen_width - 400) // 2
        picker.geometry(f"400x500+{pos_x}+50")
        picker.grab_set()

        tree = ttk.Treeview(picker, columns=("type", "id"), selectmode="browse")
        tree.heading("#0", text="Роль / Под-роль")
        tree.column("#0", width=350)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        roles = sorted(self.roles_repo.get_all(), key=lambda r: r[0])
        for r in roles:
            role_text = f"{r[0]}. {r[1]}"
            r_node = tree.insert("", "end", text=role_text, values=("role", r[0]))

            sub_roles = sorted(self.sub_roles_repo.get_by_parent(r[0]), key=lambda sr: sr[0])
            for sr in sub_roles:
                tree.insert(r_node, "end", text=sr[1], values=("sub_role", sr[0]),
                            tags=(f"parent_{r[0]}",))

        frame_btns = tk.Frame(picker)
        frame_btns.pack(fill="x", pady=10, padx=10)

        def clear_role():
            self.sheet.set_cell_data(row, 5, "")
            self._save_row(row)
            tree.selection_remove(tree.selection())

        def clear_sub_role():
            self.sheet.set_cell_data(row, 6, "")
            self._save_row(row)
            tree.selection_remove(tree.selection())

        tk.Button(frame_btns, text="Очистить роль", command=clear_role, fg="red").pack(side="left", padx=5)
        tk.Button(frame_btns, text="Очистить под-роль", command=clear_sub_role, fg="red").pack(side="left", padx=5)

        def select_item(event=None):
            selected = tree.selection()
            if not selected:
                return
            item = tree.item(selected[0])
            val_type = item["values"][0]
            val_id = item["values"][1]

            current_role_name = self.sheet.get_cell_data(row, 5)
            current_sub_name = self.sheet.get_cell_data(row, 6)

            if val_type == "role":
                if current_sub_name:
                    current_sub_id = self.sub_roles_map.get(current_sub_name)
                    if current_sub_id:
                        conn = self.sub_roles_repo.db.connect()
                        parent_id = conn.execute(
                            "SELECT parent_role_id FROM sub_roles WHERE id=?", (current_sub_id,)
                        ).fetchone()[0]
                        conn.close()
                        if str(parent_id) != str(val_id):
                            messagebox.showerror(
                                "Ошибка",
                                "Сначала очистите под-роль, так как она принадлежит другой роли."
                            )
                            return

                role_name = item["text"].split(". ", 1)[1]
                self.sheet.set_cell_data(row, 5, role_name)

            else:
                if current_role_name:
                    current_role_id = self.roles_map.get(current_role_name)
                    parent_role_id = item["tags"][0].replace("parent_", "")
                    if current_role_id and str(current_role_id) != str(parent_role_id):
                        messagebox.showerror(
                            "Ошибка",
                            "Сначала очистите роль, так как она не соответствует родителю этой под-роли."
                        )
                        return

                self.sheet.set_cell_data(row, 6, item["text"])

                parent_role_id = item["tags"][0].replace("parent_", "")
                for r in self.roles_repo.get_all():
                    if str(r[0]) == str(parent_role_id):
                        self.sheet.set_cell_data(row, 5, r[1])
                        break

            self._save_row(row)
            picker.destroy()

        tree.bind("<Double-Button-1>", select_item)
        tk.Button(frame_btns, text="Выбрать", command=select_item).pack(side="right", padx=5)

    def _load_state(self):
        try:
            widths = json.loads(self.prefs_repo.get("regular_duties_col_widths"))
            if isinstance(widths, list) and len(widths) == 9 and all(w is not None for w in widths):
                self.sheet.set_column_widths([int(w) for w in widths])
            else:
                raise ValueError()
        except Exception:
            self.sheet.set_column_widths([70, 150, 200, 150, 80, 150, 150, 80, 50])

    def save_state(self):
        widths = self.sheet.get_column_widths()
        self.prefs_repo.set("regular_duties_col_widths", json.dumps(widths))
        self.prefs_repo.set("regular_duties_sort_col", self.sort_col)
        self.prefs_repo.set("regular_duties_sort_asc", self.sort_asc)

    def refresh_table(self):
        # Справочники
        self.roles_map = {r[1]: r[0] for r in self.roles_repo.get_all()}
        self.roles_id_to_name = {r[0]: r[1] for r in self.roles_repo.get_all()}

        self.sub_roles_map = {}
        self.sub_roles_id_to_name = {}
        for r in self.roles_repo.get_all():
            for sr in self.sub_roles_repo.get_by_parent(r[0]):
                self.sub_roles_map[sr[1]] = sr[0]
                self.sub_roles_id_to_name[sr[0]] = sr[1]

        self.types_map = {}
        self.types_id_to_name = {}
        for t in self.types_repo.get_all():
            self.types_map[t[1]] = t[0]
            self.types_id_to_name[t[0]] = t[1]

        duties = self.duties_repo.get_all()
        data = []
        for d in duties:
            # d = (id, name, description, execution_order, importance, activity_type_id, period_type, role_id, sub_role_id, created_at, updated_at)
            d_id, d_name, d_desc, d_ord, d_imp, d_type_id, d_period, d_role_id, d_sub_id = d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8]
            type_name = self.types_id_to_name.get(d_type_id, "")
            role_name = self.roles_id_to_name.get(d_role_id, "")
            sub_role_name = self.sub_roles_id_to_name.get(d_sub_id, "")
            data.append([d_ord, d_name, d_desc or "", type_name, d_period, role_name, sub_role_name, d_imp, d_id])

        data = sort_sheet_data(data, self.sort_col, self.sort_asc, numeric_cols=[0, 7, 8])
        self.sheet.set_sheet_data(data, reset_col_positions=False)

    def _save_row(self, row):
        duty_id = self.sheet.get_cell_data(row, 8)
        ord_val = self.sheet.get_cell_data(row, 0)
        name = self.sheet.get_cell_data(row, 1)
        desc = self.sheet.get_cell_data(row, 2)
        type_name = self.sheet.get_cell_data(row, 3)
        period = self.sheet.get_cell_data(row, 4)
        role_name = self.sheet.get_cell_data(row, 5)
        sub_role_name = self.sheet.get_cell_data(row, 6)
        imp_val = self.sheet.get_cell_data(row, 7)

        try:
            execution_order = int(float(ord_val)) if str(ord_val).strip() else None
        except (ValueError, TypeError):
            execution_order = None
        # Показываем разобранное значение, а не пустоту: раньше здесь
        # ставился "", и следующая правка любого поля писала в БД NULL.
        self.sheet.set_cell_data(
            row, 0, execution_order if execution_order is not None else ""
        )

        try:
            importance = int(float(imp_val)) if str(imp_val).strip() else None
        except (ValueError, TypeError):
            importance = None
        self.sheet.set_cell_data(
            row, 7, importance if importance is not None else ""
        )

        type_id = self.types_map.get(type_name)
        role_id = self.roles_map.get(role_name) if role_name else None
        sub_role_id = self.sub_roles_map.get(sub_role_name) if sub_role_name else None

        if not name or not str(name).strip():
            messagebox.showwarning("Ошибка", "Название регулярной обязанности не может быть пустым!")
            self.refresh_table()
            return

        if not type_id:
            messagebox.showwarning("Ошибка", "Выберите тип активности для регулярной обязанности!")
            self.refresh_table()
            return

        if period not in ("day", "week", "month"):
            messagebox.showwarning("Ошибка", "Выберите корректный период (day/week/month)!")
            self.refresh_table()
            return

        try:
            self.duties_repo.update(duty_id, name, desc, type_id, period, role_id, sub_role_id, execution_order, importance)
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка", "Обязанность с таким названием уже существует!")
            self.refresh_table()
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось сохранить изменение:\n{e}")
            self.refresh_table()

    def on_cell_edited(self, event):
        row = event.row
        col = event.column
        if col in [3, 4, 5, 6, 8]:
            return

        name = self.sheet.get_cell_data(row, 1)
        if not name or not str(name).strip():
            messagebox.showwarning("Ошибка", "Название регулярной обязанности не может быть пустым!")
            self.refresh_table()
            return

        self._save_row(row)
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
        self.save_state()
        self.refresh_table()

    def on_add_row(self):
        try:
            types = self.types_repo.get_all()
            if not types:
                messagebox.showwarning("Ошибка", "Сначала создайте хотя бы один тип активности!")
                return
            default_type_id = types[0][0]
            self.duties_repo.add("Новая регулярная обязанность", "", default_type_id, "week", None, None, None, None)
            self.refresh_table()
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка", "Регулярная обязанность с таким названием уже существует!")
            self.refresh_table()
        except Exception as e:
            messagebox.showerror("Ошибка БД", f"Не удалось добавить регулярную обязанность:\n{e}")

    def on_delete_row(self):
        selected = self.sheet.get_currently_selected()
        row = getattr(selected, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите регулярную обязанность для удаления!")
            return
        duty_id = self.sheet.get_cell_data(row, 8)

        if messagebox.askyesno("Подтверждение", "Удалить выбранную регулярную обязанность?"):
            try:
                self.duties_repo.delete(duty_id)
                self.refresh_table()
            except sqlite3.IntegrityError:
                messagebox.showerror(
                    "Ошибка",
                    "Нельзя удалить эту регулярную обязанность: с ней связаны активности или отметки."
                )
            except Exception as e:
                messagebox.showerror("Ошибка БД", f"Не удалось удалить регулярную обязанность:\n{e}")