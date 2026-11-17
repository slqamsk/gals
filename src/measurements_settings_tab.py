# src/measurements_settings_tab.py
# Вкладка «Настройки»: типы+компоненты (Master-Detail) и единицы.
#
# В preferences сохраняются: ширины колонок трёх таблиц и позиция
# разделителя «типы | компоненты». Ширины пишутся JSON-строкой
# (конвенция из шапки defaults.py).
import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from tksheet import Sheet


class MeasurementsSettingsTab(tk.Frame):
    WIDTHS_TYPES = [50, 200, 300]
    WIDTHS_COMPS = [50, 150, 120, 80, 80]
    WIDTHS_UNITS = [50, 100, 200, 300]

    def __init__(self, parent, repo, prefs_repo):
        super().__init__(parent)
        self.repo = repo
        self.prefs_repo = prefs_repo
        self.current_type_id = None

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self.tab_tc = self._build_types_components_tab()
        self.notebook.add(self.tab_tc, text="Типы и компоненты")

        self.tab_units = self._build_units_tab()
        self.notebook.add(self.tab_units, text="Единицы")

        self.refresh_all()
        self._load_widths()
        # При уходе с подвкладки сохраняем её ширины (в т.ч. неактивной таблицы).
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    # ---------- Сохранение / восстановление GUI ----------
    def _get_widths(self, key: str, default: list[int]) -> list[int]:
        """Читает ширины из prefs (JSON-строка). Мусор/пусто → дефолт."""
        try:
            raw = self.prefs_repo.get(key)
            widths = json.loads(raw) if isinstance(raw, str) else raw
            if (isinstance(widths, list) and len(widths) == len(default)
                    and all(w is not None for w in widths)):
                return [int(w) for w in widths]
        except Exception:
            pass
        return list(default)

    def _load_widths(self):
        """Применяется один раз при создании вкладок.

        При обновлении данных вызывать нельзя — иначе сбросятся ширины,
        которые пользователь подвинул мышью, но ещё не сохранил.
        """
        try:
            self.sheet_types.set_column_widths(
                self._get_widths("measurements_types_col_widths", self.WIDTHS_TYPES))
            self.sheet_comps.set_column_widths(
                self._get_widths("measurements_components_col_widths", self.WIDTHS_COMPS))
            self.sheet_units.set_column_widths(
                self._get_widths("measurements_units_col_widths", self.WIDTHS_UNITS))
        except Exception:
            pass

    def _on_tab_changed(self, event=None):
        self.save_state()

    def save_state(self):
        for sheet, key in (
            (self.sheet_types, "measurements_types_col_widths"),
            (self.sheet_comps, "measurements_components_col_widths"),
            (self.sheet_units, "measurements_units_col_widths"),
        ):
            try:
                widths = sheet.get_column_widths()
                # Неотрисованная таблица может вернуть нули — такие не пишем.
                if widths and all(int(w) > 0 for w in widths):
                    self.prefs_repo.set(key, json.dumps([int(w) for w in widths]))
            except Exception:
                pass

    # ---------- Типы и компоненты ----------
    def _build_types_components_tab(self):
        frame = tk.Frame(self.notebook)

        self.paned = tk.PanedWindow(frame, orient="horizontal", sashwidth=5)
        self.paned.pack(fill="both", expand=True, padx=5, pady=5)

        # Левая панель — типы
        frame_types = tk.Frame(self.paned)
        self.paned.add(frame_types, stretch="always")

        frame_btns_t = tk.Frame(frame_types)
        frame_btns_t.pack(fill="x", pady=3)
        tk.Label(frame_btns_t, text="Типы измерений",
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(frame_btns_t, text="Добавить",
                  command=self._add_type).pack(side="right", padx=2)
        tk.Button(frame_btns_t, text="Удалить", fg="red",
                  command=self._delete_type).pack(side="right", padx=2)

        self.sheet_types = Sheet(
            frame_types,
            headers=["ID", "Имя", "Описание"],
            show_row_index=False, show_top_left=False,
            show_x_scrollbar=True, show_y_scrollbar=True,
            table_grid_fg="#000000", outline_thickness=1,
            header_bg="#f0f0f0", header_fg="#000000",
            font=("Arial", 9, "normal"), header_font=("Arial", 9, "bold"),
            row_height=25, table_wrap="w", auto_resize_row_heights=True,
        )
        self.sheet_types.pack(fill="both", expand=True)
        self.sheet_types.enable_bindings("all")
        self.sheet_types.readonly_columns(columns=[0])
        self.sheet_types.extra_bindings("end_edit_cell", self._on_type_edited)
        self.sheet_types.MT.bind("<ButtonRelease-1>", self._on_type_select, add="+")

        # Правая панель — компоненты
        frame_comps = tk.Frame(self.paned)
        self.paned.add(frame_comps, stretch="always")

        frame_btns_c = tk.Frame(frame_comps)
        frame_btns_c.pack(fill="x", pady=3)
        self.lbl_comps_title = tk.Label(frame_btns_c, text="Компоненты",
                                        font=("Arial", 10, "bold"))
        self.lbl_comps_title.pack(side="left")
        tk.Button(frame_btns_c, text="Добавить",
                  command=self._add_component).pack(side="right", padx=2)
        tk.Button(frame_btns_c, text="Удалить", fg="red",
                  command=self._delete_component).pack(side="right", padx=2)

        self.sheet_comps = Sheet(
            frame_comps,
            headers=["ID", "Имя", "Единица", "Порядок", "Обязат."],
            show_row_index=False, show_top_left=False,
            show_x_scrollbar=True, show_y_scrollbar=True,
            table_grid_fg="#000000", outline_thickness=1,
            header_bg="#f0f0f0", header_fg="#000000",
            font=("Arial", 9, "normal"), header_font=("Arial", 9, "bold"),
            row_height=25, table_wrap="w", auto_resize_row_heights=True,
        )
        self.sheet_comps.pack(fill="both", expand=True)
        self.sheet_comps.enable_bindings("all")
        self.sheet_comps.readonly_columns(columns=[0, 2, 4])
        self.sheet_comps.extra_bindings("end_edit_cell", self._on_component_edited)
        self.sheet_comps.MT.bind("<Double-Button-1>", self._on_comp_dblclick, add="+")

        # Восстановление sash позиции
        try:
            sash_pos = self.prefs_repo.get("measurements_settings_sash")
            if isinstance(sash_pos, int):
                self.after(50, lambda: self._restore_sash(sash_pos))
        except Exception:
            pass
        self.paned.bind("<ButtonRelease-1>", self._save_sash)

        return frame

    def _restore_sash(self, pos):
        try:
            self.paned.sash_place(0, pos, 0)
        except tk.TclError:
            pass

    def _save_sash(self, event=None):
        try:
            x, y = self.paned.sash_coord(0)
            self.prefs_repo.set("measurements_settings_sash", x)
        except Exception:
            pass

    def _load_types(self):
        types = self.repo.get_all_types()
        rows = [[t[0], t[1], t[2] or ""] for t in types]
        self.sheet_types.set_sheet_data(rows, reset_col_positions=False)

        if self.current_type_id is not None:
            for i, r in enumerate(rows):
                if r[0] == self.current_type_id:
                    self._select_sheet_row(self.sheet_types, i)
                    self._load_components()
                    return

        if rows:
            self.current_type_id = rows[0][0]
            self._select_sheet_row(self.sheet_types, 0)
            self._load_components()
        else:
            self.current_type_id = None
            self._load_components()

    def _select_sheet_row(self, sheet, idx):
        try:
            sheet.select_row(idx)
        except Exception:
            pass

    def _on_type_select(self, event=None):
        sel = self.sheet_types.get_currently_selected()
        row = getattr(sel, "row", None)
        if row is None:
            return
        tid = self.sheet_types.get_cell_data(row, 0)
        try:
            self.current_type_id = int(tid)
        except (ValueError, TypeError):
            return
        self._load_components()

    def _load_components(self):
        if self.current_type_id is None:
            self.sheet_comps.set_sheet_data([])
            self.lbl_comps_title.config(text="Компоненты (тип не выбран)")
            return

        self.lbl_comps_title.config(text=f"Компоненты типа #{self.current_type_id}")
        comps = self.repo.get_components_for_type(self.current_type_id)
        rows = [
            [c[0], c[1], c[3], c[4], "Да" if c[5] else "Нет"]
            for c in comps
        ]
        self.sheet_comps.set_sheet_data(rows, reset_col_positions=False)

    def _on_type_edited(self, event):
        row = event.row
        tid = self.sheet_types.get_cell_data(row, 0)
        try:
            tid = int(tid)
        except (ValueError, TypeError):
            return

        name = self.sheet_types.get_cell_data(row, 1)
        desc = self.sheet_types.get_cell_data(row, 2) or ""

        if not name or not str(name).strip():
            messagebox.showwarning("Ошибка", "Имя типа не может быть пустым")
            self._load_types()
            return

        try:
            self.repo.update_type(tid, str(name).strip(), str(desc).strip() or None)
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка", "Тип с таким именем уже существует")
            self._load_types()
            return
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            self._load_types()
            return

        self._load_types()

    def _add_type(self):
        try:
            self.repo.add_type("Новый тип", None)
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка", "Не удалось добавить: имя занято")
            return
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            return
        self._load_types()

    def _delete_type(self):
        if self.current_type_id is None:
            messagebox.showwarning("Внимание", "Выберите тип для удаления")
            return

        comps_cnt, sessions_cnt = self.repo.get_type_usage(self.current_type_id)
        if comps_cnt > 0:
            messagebox.showerror(
                "Ошибка удаления",
                f"У типа есть компоненты ({comps_cnt}). Удалите их сначала."
            )
            return
        if sessions_cnt > 0:
            messagebox.showerror(
                "Ошибка удаления",
                f"У типа есть сеансы измерений ({sessions_cnt}). Удалить нельзя."
            )
            return

        if not messagebox.askyesno("Подтверждение",
                                   f"Удалить тип #{self.current_type_id}?"):
            return

        try:
            self.repo.delete_type(self.current_type_id)
        except sqlite3.IntegrityError as e:
            messagebox.showerror("Ошибка удаления", f"Нельзя удалить: {e}")
            return
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            return

        self.current_type_id = None
        self._load_types()

    # --- Компоненты ---
    def _on_comp_dblclick(self, event):
        row = self.sheet_comps.identify_row(event)
        col = self.sheet_comps.identify_column(event)
        if row == "" or col == "":
            return
        try:
            row = int(row)
            col = int(col)
        except ValueError:
            return

        if col == 2:
            self._open_unit_picker(row)
        elif col == 4:
            self._toggle_required(row)

    def _toggle_required(self, row):
        comp_id = self.sheet_comps.get_cell_data(row, 0)
        try:
            comp_id = int(comp_id)
        except (ValueError, TypeError):
            return
        comp = self.repo.get_component_by_id(comp_id)
        if not comp:
            return
        new_req = 0 if comp[5] else 1
        try:
            self.repo.update_component(comp_id, comp[2], comp[3], comp[4], new_req)
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            return
        self._load_components()

    def _open_unit_picker(self, row):
        comp_id = self.sheet_comps.get_cell_data(row, 0)
        try:
            comp_id = int(comp_id)
        except (ValueError, TypeError):
            return

        units = self.repo.get_all_units()
        if not units:
            messagebox.showwarning("Ошибка", "В справочнике нет единиц")
            return

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Выбор единицы")
        dialog.geometry("400x450")
        dialog.grab_set()

        tree = ttk.Treeview(dialog, columns=("id", "full"), selectmode="browse")
        tree.heading("#0", text="Краткое")
        tree.heading("id", text="ID")
        tree.heading("full", text="Полное")
        tree.column("#0", width=100)
        tree.column("id", width=50)
        tree.column("full", width=200)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for u in units:
            tree.insert("", "end", text=u[1], values=(u[0], u[2]))

        def select():
            sel = tree.selection()
            if not sel:
                return
            item = tree.item(sel[0])
            unit_id = item["values"][0]
            comp = self.repo.get_component_by_id(comp_id)
            if not comp:
                return
            try:
                self.repo.update_component(comp_id, comp[2], int(unit_id),
                                           comp[4], comp[5])
            except Exception as e:
                messagebox.showerror("Ошибка БД", str(e), parent=dialog)
                return
            dialog.destroy()
            self._load_components()

        tree.bind("<Double-Button-1>", lambda e: select())
        tk.Button(dialog, text="Выбрать", command=select).pack(pady=10)

    def _on_component_edited(self, event):
        row = event.row
        col = event.column
        if col in [0, 2, 4]:
            return

        comp_id = self.sheet_comps.get_cell_data(row, 0)
        try:
            comp_id = int(comp_id)
        except (ValueError, TypeError):
            return

        comp = self.repo.get_component_by_id(comp_id)
        if not comp:
            return

        name = self.sheet_comps.get_cell_data(row, 1)
        if not name or not str(name).strip():
            messagebox.showwarning("Ошибка", "Имя не может быть пустым")
            self._load_components()
            return

        try:
            order = int(self.sheet_comps.get_cell_data(row, 3) or 1)
        except (ValueError, TypeError):
            order = 1

        try:
            self.repo.update_component(comp_id, str(name).strip(),
                                       comp[3], order, comp[5])
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка",
                                 "Компонент с таким именем уже есть в типе")
            self._load_components()
            return
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            self._load_components()
            return

        self._load_components()

    def _add_component(self):
        if self.current_type_id is None:
            messagebox.showwarning("Внимание", "Выберите тип")
            return

        units = self.repo.get_all_units()
        if not units:
            messagebox.showwarning("Ошибка", "Нет единиц. Создайте в «Единицах»")
            return

        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Новый компонент")
        dialog.geometry("420x380")
        dialog.grab_set()

        tk.Label(dialog, text="Имя:", anchor="w").pack(fill="x", padx=15, pady=(15, 0))
        ent_name = tk.Entry(dialog)
        ent_name.pack(fill="x", padx=15, pady=2)

        tk.Label(dialog, text="Единица:", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        units_map = {u[1]: u[0] for u in units}
        cb_unit = ttk.Combobox(dialog, values=list(units_map.keys()),
                               state="readonly")
        cb_unit.pack(fill="x", padx=15, pady=2)
        if units_map:
            cb_unit.set(list(units_map.keys())[0])

        tk.Label(dialog, text="Порядок:", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        ent_order = tk.Entry(dialog)
        ent_order.insert(0, "1")
        ent_order.pack(fill="x", padx=15, pady=2)

        var_req = tk.BooleanVar(value=True)
        tk.Checkbutton(dialog, text="Обязательный",
                       variable=var_req).pack(anchor="w", padx=15, pady=(10, 5))

        def save():
            name = ent_name.get().strip()
            if not name:
                messagebox.showerror("Ошибка", "Имя не может быть пустым", parent=dialog)
                return
            unit_name = cb_unit.get()
            unit_id = units_map.get(unit_name)
            if not unit_id:
                messagebox.showerror("Ошибка", "Выберите единицу", parent=dialog)
                return
            try:
                order = int(ent_order.get())
            except ValueError:
                order = 1
            try:
                self.repo.add_component(
                    measurement_type_id=self.current_type_id,
                    name=name,
                    unit_id=unit_id,
                    display_order=order,
                    is_required=1 if var_req.get() else 0,
                )
            except sqlite3.IntegrityError:
                messagebox.showerror("Ошибка",
                                     "Компонент с таким именем уже есть",
                                     parent=dialog)
                return
            except Exception as e:
                messagebox.showerror("Ошибка БД", str(e), parent=dialog)
                return
            dialog.destroy()
            self._load_components()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=15)
        tk.Button(frame_btns, text="Сохранить", command=save,
                  width=12).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=dialog.destroy,
                  width=12).pack(side="left", padx=5)

    def _delete_component(self):
        sel = self.sheet_comps.get_currently_selected()
        row = getattr(sel, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите компонент")
            return
        comp_id = self.sheet_comps.get_cell_data(row, 0)
        try:
            comp_id = int(comp_id)
        except (ValueError, TypeError):
            return

        usage = self.repo.get_component_usage(comp_id)
        if usage > 0:
            messagebox.showerror(
                "Ошибка удаления",
                f"У компонента есть значения ({usage}). Удалить нельзя."
            )
            return

        if not messagebox.askyesno("Подтверждение",
                                   f"Удалить компонент #{comp_id}?"):
            return

        try:
            self.repo.delete_component(comp_id)
        except sqlite3.IntegrityError as e:
            messagebox.showerror("Ошибка", f"Нельзя удалить: {e}")
            return
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            return

        self._load_components()

    # ---------- Единицы ----------
    def _build_units_tab(self):
        frame = tk.Frame(self.notebook)

        frame_btns = tk.Frame(frame)
        frame_btns.pack(fill="x", padx=10, pady=5)
        tk.Label(frame_btns, text="Единицы измерения",
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(frame_btns, text="Добавить",
                  command=self._add_unit).pack(side="right", padx=2)
        tk.Button(frame_btns, text="Удалить", fg="red",
                  command=self._delete_unit).pack(side="right", padx=2)

        self.sheet_units = Sheet(
            frame,
            headers=["ID", "Краткое", "Полное", "Описание"],
            show_row_index=False, show_top_left=False,
            show_x_scrollbar=True, show_y_scrollbar=True,
            table_grid_fg="#000000", outline_thickness=1,
            header_bg="#f0f0f0", header_fg="#000000",
            font=("Arial", 9, "normal"), header_font=("Arial", 9, "bold"),
            row_height=25, table_wrap="w", auto_resize_row_heights=True,
        )
        self.sheet_units.pack(fill="both", expand=True, padx=10, pady=5)
        self.sheet_units.enable_bindings("all")
        self.sheet_units.readonly_columns(columns=[0])
        self.sheet_units.extra_bindings("end_edit_cell", self._on_unit_edited)

        return frame

    def _load_units(self):
        units = self.repo.get_all_units()
        rows = [[u[0], u[1], u[2], u[3] or ""] for u in units]
        self.sheet_units.set_sheet_data(rows, reset_col_positions=False)

    def _on_unit_edited(self, event):
        row = event.row
        uid = self.sheet_units.get_cell_data(row, 0)
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return

        dn = self.sheet_units.get_cell_data(row, 1)
        fn = self.sheet_units.get_cell_data(row, 2)
        desc = self.sheet_units.get_cell_data(row, 3) or ""

        if not dn or not fn:
            messagebox.showwarning("Ошибка",
                                   "Краткое и полное имена обязательны")
            self._load_units()
            return

        try:
            self.repo.update_unit(uid, str(dn).strip(), str(fn).strip(),
                                  str(desc).strip() or None)
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка", "Такое краткое имя уже есть")
            self._load_units()
            return
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            self._load_units()
            return

        self._load_units()
        self._load_components()

    def _add_unit(self):
        try:
            self.repo.add_unit("новая", "новая единица", None)
        except sqlite3.IntegrityError:
            messagebox.showerror("Ошибка", "Имя занято")
            return
        self._load_units()

    def _delete_unit(self):
        sel = self.sheet_units.get_currently_selected()
        row = getattr(sel, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите единицу")
            return
        uid = self.sheet_units.get_cell_data(row, 0)
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            return

        usage = self.repo.get_units_usage(uid)
        if usage:
            usage_str = "; ".join(f"«{c}» типа «{t}»" for c, t in usage)
            messagebox.showerror(
                "Ошибка удаления",
                f"Единица используется в компонентах: {usage_str}"
            )
            return

        if not messagebox.askyesno("Подтверждение",
                                   f"Удалить единицу #{uid}?"):
            return

        try:
            self.repo.delete_unit(uid)
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))
            return
        self._load_units()

    # ---------- Общее ----------
    def refresh_all(self):
        self._load_types()
        self._load_units()