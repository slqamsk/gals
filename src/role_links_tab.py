# src/role_links_tab.py
# Вкладка «Связи ролей» (внутри верхней вкладки «Дерево ролей»).
# 3 панели: дерево ролей, типы активностей, обязанности.
# 3 варианта компоновки:
#   v1 «Вертикально»   — 3 вертикальные панели (слева направо)
#   v2 «С-образно»     — дерево слева, типы сверху справа, обязанности снизу справа
#   v3 «Горизонтально» — 3 горизонтальные панели (сверху вниз)
# Панели можно скрывать чекбоксами (Типы активностей / Обязанности).
# Редактирование ячеек — прямо в таблице. Добавление — через диалог.
#
# Изменения:
#   - Кнопка «Обновить» в верхней панели.
#   - Диалоги добавления: первыми идут Роль/Под-роль (предзаполнены
#     из текущего выделения в дереве, но их можно изменить),
#     все поля растянуты по ширине окна, размер окон увеличен.
#   - В «Добавить обязанность» тип активности фильтруется по роли/подроли
#     и предзаполняется из текущего выделения в таблице типов.
#   - Удаление: ловим sqlite3.IntegrityError и пишем по-русски с именем записи.
#   - Состояние "свёрнуто/развёрнуто" дерева ролей хранится в preferences
#     (roles_tree_state) и общее для всех вкладок с деревом ролей.

import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from tksheet import Sheet

from .roles_repo import RolesRepository
from .sub_roles_repo import SubRolesRepository
from .activity_types_repo import ActivityTypesRepository
from .regular_duties_repo import RegularDutiesRepository
from .preferences_repo import PreferencesRepository
from .ui_utils import sort_sheet_data


class RoleLinksTab(tk.Frame):
    def __init__(self, parent, roles_repo, sub_roles_repo, types_repo, duties_repo, prefs_repo):
        super().__init__(parent)
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.types_repo = types_repo
        self.duties_repo = duties_repo
        self.prefs_repo = prefs_repo

        self.current_role_id = None
        self.current_sub_role_id = None

        self.types_data = []
        self.duties_data = []
        self.roles_id_to_name = {}
        self.sub_roles_id_to_name = {}
        self.types_id_to_name = {}

        self.sheet_types = None
        self.sheet_duties = None

        self.types_sort_col = self.prefs_repo.get("role_links_types_sort_col")
        if self.types_sort_col is None:
            self.types_sort_col = 0
        self.types_sort_asc = self.prefs_repo.get("role_links_types_sort_asc")
        if self.types_sort_asc is None:
            self.types_sort_asc = True

        self.duties_sort_col = self.prefs_repo.get("role_links_duties_sort_col")
        if self.duties_sort_col is None:
            self.duties_sort_col = 0
        self.duties_sort_asc = self.prefs_repo.get("role_links_duties_sort_asc")
        if self.duties_sort_asc is None:
            self.duties_sort_asc = True

        # Стиль для дерева (крупнее строки)
        style = ttk.Style()
        style.configure("RoleLinks.Treeview", rowheight=28, font=("Arial", 10))

        # Верхняя панель с переключателем layout
        self.frame_top = tk.Frame(self)
        self.frame_top.pack(fill="x", padx=10, pady=5)

        tk.Label(self.frame_top, text="Расположение:").pack(side="left")
        self.layout_var = tk.StringVar(value=self.prefs_repo.get("role_links_layout") or "v1")

        tk.Radiobutton(self.frame_top, text="Вертикально", variable=self.layout_var,
                       value="v1", command=self._change_layout).pack(side="left", padx=5)
        tk.Radiobutton(self.frame_top, text="С-образно", variable=self.layout_var,
                       value="v2", command=self._change_layout).pack(side="left", padx=5)
        tk.Radiobutton(self.frame_top, text="Горизонтально", variable=self.layout_var,
                       value="v3", command=self._change_layout).pack(side="left", padx=5)

        tk.Label(self.frame_top, text="|").pack(side="left", padx=10)

        show_types_val = self.prefs_repo.get("role_links_show_types")
        if show_types_val is None:
            show_types_val = True

        show_duties_val = self.prefs_repo.get("role_links_show_duties")
        if show_duties_val is None:
            show_duties_val = True

        self.show_types_var = tk.BooleanVar(value=bool(show_types_val))
        self.show_duties_var = tk.BooleanVar(value=bool(show_duties_val))

        tk.Checkbutton(self.frame_top, text="Типы активностей", variable=self.show_types_var,
                       command=self._on_visibility_changed).pack(side="left", padx=2)
        tk.Checkbutton(self.frame_top, text="Обязанности", variable=self.show_duties_var,
                       command=self._on_visibility_changed).pack(side="left", padx=2)

        # Кнопка «Обновить»
        tk.Button(self.frame_top, text="Обновить", command=self.refresh_all).pack(side="right", padx=5)

        self.layout_container = tk.Frame(self)
        self.layout_container.pack(fill="both", expand=True, padx=10, pady=5)

        self._apply_layout()
        self.refresh_all()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _change_layout(self):
        self.prefs_repo.set("role_links_layout", self.layout_var.get())
        self._apply_layout()
        self.refresh_all()

    def _on_visibility_changed(self):
        self.prefs_repo.set("role_links_show_types", self.show_types_var.get())
        self.prefs_repo.set("role_links_show_duties", self.show_duties_var.get())
        self._apply_layout()
        self.refresh_all()

    def _apply_layout(self):
        self._save_current_widths()

        for widget in self.layout_container.winfo_children():
            widget.destroy()

        self.sheet_types = None
        self.sheet_duties = None

        layout = self.layout_var.get()
        sashes = self.prefs_repo.get("role_links_sashes") or {}

        show_types = self.show_types_var.get()
        show_duties = self.show_duties_var.get()

        base_key = f"{layout}_{int(show_types)}_{int(show_duties)}"

        if layout == "v1":
            paned = tk.PanedWindow(self.layout_container, orient="horizontal", sashwidth=5)
            paned.pack(fill="both", expand=True)

            paned.add(self._build_tree_pane(paned), stretch="always", width=350)
            if show_types:
                paned.add(self._build_types_pane(paned), stretch="always", width=800)
            if show_duties:
                paned.add(self._build_duties_pane(paned), stretch="always", width=800)

            self._bind_sash_save_safely(paned, base_key, [350, 1150], sashes)

        elif layout == "v2":
            if show_types and show_duties:
                paned_outer = tk.PanedWindow(self.layout_container, orient="horizontal", sashwidth=5)
                paned_outer.pack(fill="both", expand=True)

                paned_inner = tk.PanedWindow(paned_outer, orient="vertical", sashwidth=5)
                paned_inner.add(self._build_types_pane(paned_inner), stretch="always", height=400)
                paned_inner.add(self._build_duties_pane(paned_inner), stretch="always", height=400)

                paned_outer.add(self._build_tree_pane(paned_outer), stretch="always", width=350)
                paned_outer.add(paned_inner, stretch="always", width=1000)

                self._bind_sash_save_safely(paned_outer, base_key + "_outer", [350], sashes)
                self._bind_sash_save_safely(paned_inner, base_key + "_inner", [400], sashes)
            else:
                paned = tk.PanedWindow(self.layout_container, orient="horizontal", sashwidth=5)
                paned.pack(fill="both", expand=True)

                paned.add(self._build_tree_pane(paned), stretch="always", width=350)
                if show_types:
                    paned.add(self._build_types_pane(paned), stretch="always", width=1000)
                if show_duties:
                    paned.add(self._build_duties_pane(paned), stretch="always", width=1000)

                self._bind_sash_save_safely(paned, base_key, [350], sashes)

        elif layout == "v3":
            paned = tk.PanedWindow(self.layout_container, orient="vertical", sashwidth=5)
            paned.pack(fill="both", expand=True)

            paned.add(self._build_tree_pane(paned), stretch="always", height=200)
            if show_types:
                paned.add(self._build_types_pane(paned), stretch="always", height=400)
            if show_duties:
                paned.add(self._build_duties_pane(paned), stretch="always", height=400)

            self._bind_sash_save_safely(paned, base_key, [200, 600], sashes)

        self.after(50, self._resize_sheets)

    def _resize_sheets(self):
        try:
            if self.sheet_types:
                types_w = self.prefs_repo.get("role_links_types_col_widths")
                if not types_w or not isinstance(types_w, list) or len(types_w) != 7:
                    types_w = [150, 150, 100, 100, 60, 60, 40]
                self.sheet_types.set_column_widths(types_w)

            if self.sheet_duties:
                duties_w = self.prefs_repo.get("role_links_duties_col_widths")
                if not duties_w or not isinstance(duties_w, list) or len(duties_w) != 9:
                    duties_w = [70, 150, 150, 150, 60, 100, 100, 70, 40]
                self.sheet_duties.set_column_widths(duties_w)
        except Exception:
            pass

    def _save_current_widths(self):
        try:
            if self.sheet_types and self.sheet_types.winfo_exists():
                self.prefs_repo.set("role_links_types_col_widths", self.sheet_types.get_column_widths())
            if self.sheet_duties and self.sheet_duties.winfo_exists():
                self.prefs_repo.set("role_links_duties_col_widths", self.sheet_duties.get_column_widths())
        except Exception:
            pass

    def save_state(self):
        self._save_current_widths()
        self.prefs_repo.set("role_links_types_sort_col", self.types_sort_col)
        self.prefs_repo.set("role_links_types_sort_asc", self.types_sort_asc)
        self.prefs_repo.set("role_links_duties_sort_col", self.duties_sort_col)
        self.prefs_repo.set("role_links_duties_sort_asc", self.duties_sort_asc)

    def _bind_sash_save_safely(self, paned, key_prefix, default_sashes, all_sashes):
        expected_len = len(paned.panes()) - 1
        if expected_len <= 0:
            return

        saved = all_sashes.get(key_prefix, [])

        if not isinstance(saved, list) or len(saved) != expected_len:
            saved = default_sashes[:expected_len]
            if len(saved) < expected_len:
                saved = [100 + i * 100 for i in range(expected_len)]

        self._bind_sash_save(paned, key_prefix, saved)

    def _bind_sash_save(self, paned, key, default_sashes):
        def restore():
            paned.update_idletasks()
            orient = str(paned.cget("orient"))
            for i, pos in enumerate(default_sashes):
                try:
                    if orient == "horizontal":
                        paned.sash_place(i, pos, 0)
                    else:
                        paned.sash_place(i, 0, pos)
                except tk.TclError:
                    pass
        self.after(50, restore)

        def save(event=None):
            try:
                orient = str(paned.cget("orient"))
                positions = []
                for i in range(len(paned.panes()) - 1):
                    x, y = paned.sash_coord(i)
                    positions.append(x if orient == "horizontal" else y)
                all_sashes = self.prefs_repo.get("role_links_sashes") or {}
                all_sashes[key] = positions
                self.prefs_repo.set("role_links_sashes", all_sashes)
            except Exception:
                pass

        paned.bind("<ButtonRelease-1>", save)

    # ------------------------------------------------------------------
    # Построение панелей
    # ------------------------------------------------------------------
    def _build_tree_pane(self, parent):
        frame = tk.Frame(parent)

        frame_header = tk.Frame(frame)
        frame_header.pack(fill="x")
        tk.Label(frame_header, text="Роли / Под-роли:", font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(frame_header, text="Развернуть", font=("Arial", 8),
                  command=self._expand_all_roles).pack(side="right", padx=2)
        tk.Button(frame_header, text="Свернуть", font=("Arial", 8),
                  command=self._collapse_all_roles).pack(side="right", padx=2)

        self.tree_roles = ttk.Treeview(
            frame, show="tree", selectmode="browse",
            style="RoleLinks.Treeview",
        )
        self.tree_roles.column("#0", width=250, minwidth=180)
        self.tree_roles.pack(fill="both", expand=True, pady=2)
        self.tree_roles.bind("<<TreeviewSelect>>", self._on_role_select)
        self.tree_roles.bind("<<TreeviewOpen>>", self._on_node_toggled)
        self.tree_roles.bind("<<TreeviewClose>>", self._on_node_toggled)

        self.tree_roles.tag_configure("role_node", font=("Arial", 11, "bold"))
        self.tree_roles.tag_configure("sub_role_node", font=("Arial", 10, "normal"))

        return frame

    # ------------------------------------------------------------------
    # Состояние дерева (общее для всех вкладок с деревом ролей)
    # ------------------------------------------------------------------
    def _get_state(self) -> dict:
        state = self.prefs_repo.get("roles_tree_state")
        if not isinstance(state, dict):
            state = {}
        return state

    def _save_state(self, state: dict):
        self.prefs_repo.set("roles_tree_state", state)

    def _on_node_toggled(self, event=None):
        """Сохраняет текущее состояние всех ролей в preferences."""
        state = self._get_state()
        for role in self.roles_repo.get_all():
            role_id = role[0]
            iid = f"role_{role_id}"
            if self.tree_roles.exists(iid):
                state[str(role_id)] = bool(self.tree_roles.item(iid, "open"))
        self._save_state(state)

    def _expand_all_roles(self):
        """Разворачивает все роли и записывает состояние (все True)."""
        roles = self.roles_repo.get_all()
        state = {str(r[0]): True for r in roles}
        self._save_state(state)
        self.tree_roles.item("root", open=True)
        for item in self.tree_roles.get_children("root"):
            if item.startswith("role_"):
                self.tree_roles.item(item, open=True)

    def _collapse_all_roles(self):
        """Сворачивает все роли и записывает состояние (все False)."""
        roles = self.roles_repo.get_all()
        state = {str(r[0]): False for r in roles}
        self._save_state(state)
        self.tree_roles.item("root", open=False)

    def _build_types_pane(self, parent):
        frame = tk.Frame(parent)

        frame_btns = tk.Frame(frame)
        frame_btns.pack(fill="x", pady=2)
        tk.Label(frame_btns, text="Типы активностей:", font=("Arial", 9, "bold")).pack(side="left")
        tk.Button(frame_btns, text="Добавить тип", command=self._open_add_type).pack(side="right", padx=2)
        tk.Button(frame_btns, text="Удалить", command=lambda: self._delete_item("type"),
                  fg="red").pack(side="right", padx=2)

        self.sheet_types = Sheet(
            frame,
            headers=["Название", "Описание", "Роль", "Под-роль", "Частота", "Важность", "ID"],
            show_row_index=False, show_top_left=False, show_x_scrollbar=True, show_y_scrollbar=True,
            table_grid_fg="#000000", outline_thickness=1, header_bg="#f0f0f0", header_fg="#000000",
            font=("Arial", 9, "normal"), header_font=("Arial", 9, "bold"),
            row_height=25, table_wrap="w", auto_resize_row_heights=True,
        )
        self.sheet_types.pack(fill="both", expand=True)
        self.sheet_types.enable_bindings("all")

        # Только Роль (2), Под-роль (3), ID (6) - readonly.
        self.sheet_types.readonly_columns(columns=[2, 3, 6])
        self.sheet_types.extra_bindings("end_edit_cell", self._on_type_cell_edited)
        self.sheet_types.extra_bindings("column_select", self._on_types_column_select)

        return frame

    def _build_duties_pane(self, parent):
        frame = tk.Frame(parent)

        frame_btns = tk.Frame(frame)
        frame_btns.pack(fill="x", pady=2)
        tk.Label(frame_btns, text="Обязанности:", font=("Arial", 9, "bold")).pack(side="left")
        tk.Button(frame_btns, text="Добавить обязанность", command=self._open_add_duty).pack(side="right", padx=2)
        tk.Button(frame_btns, text="Удалить", command=lambda: self._delete_item("duty"),
                  fg="red").pack(side="right", padx=2)

        self.sheet_duties = Sheet(
            frame,
            headers=["Порядок", "Название", "Описание", "Тип активности", "Период", "Роль", "Под-роль", "Важность", "ID"],
            show_row_index=False, show_top_left=False, show_x_scrollbar=True, show_y_scrollbar=True,
            table_grid_fg="#000000", outline_thickness=1, header_bg="#f0f0f0", header_fg="#000000",
            font=("Arial", 9, "normal"), header_font=("Arial", 9, "bold"),
            row_height=25, table_wrap="w", auto_resize_row_heights=True,
        )
        self.sheet_duties.pack(fill="both", expand=True)
        self.sheet_duties.enable_bindings("all")

        # Только Тип (3), Период (4), Роль (5), Под-роль (6), ID (8) - readonly.
        self.sheet_duties.readonly_columns(columns=[3, 4, 5, 6, 8])
        self.sheet_duties.extra_bindings("end_edit_cell", self._on_duty_cell_edited)
        self.sheet_duties.extra_bindings("column_select", self._on_duties_column_select)

        return frame

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------
    def refresh_all(self):
        self._load_tree()
        self._load_tables()

    def _load_tree(self):
        for item in self.tree_roles.get_children():
            self.tree_roles.delete(item)

        state = self._get_state()

        roles = sorted(self.roles_repo.get_all(), key=lambda r: r[0])
        self.roles_id_to_name = {r[0]: r[1] for r in roles}
        self.sub_roles_id_to_name = {}

        self.tree_roles.insert(
            "", "end", iid="root", text="📁 Все роли",
            tags=("role_node",),
            open=True,
        )

        for r in roles:
            role_id, name, _desc, color = r[0], r[1], r[2], r[3]
            color = color or "#FFFFFF"

            role_iid = f"role_{role_id}"
            role_text = f"{role_id}. {name}"

            tag_color = f"color_{role_id}"
            self.tree_roles.tag_configure(tag_color, background=color)

            is_open = state.get(str(role_id), True)

            self.tree_roles.insert(
                "root", "end", iid=role_iid, text=role_text,
                open=is_open,
                tags=("role_node", tag_color),
            )

            for sr in sorted(self.sub_roles_repo.get_by_parent(role_id), key=lambda x: x[0]):
                sr_id, sr_name = sr[0], sr[1]
                self.sub_roles_id_to_name[sr_id] = sr_name
                self.tree_roles.insert(
                    role_iid, "end", iid=f"sub_{sr_id}", text=sr_name,
                    tags=("sub_role_node", tag_color),
                )

        if self.current_sub_role_id is not None:
            iid = f"sub_{self.current_sub_role_id}"
            if self.tree_roles.exists(iid):
                self.tree_roles.selection_set(iid)
                self.tree_roles.focus(iid)
                return
        if self.current_role_id is not None:
            iid = f"role_{self.current_role_id}"
            if self.tree_roles.exists(iid):
                self.tree_roles.selection_set(iid)
                self.tree_roles.focus(iid)
                return

        if self.tree_roles.exists("root"):
            self.tree_roles.selection_set("root")
            self.tree_roles.focus("root")

    def _on_role_select(self, event):
        sel = self.tree_roles.selection()
        if not sel:
            self.current_role_id = None
            self.current_sub_role_id = None
            self._load_tables()
            return

        item_id = sel[0]
        if item_id == "root":
            self.current_role_id = None
            self.current_sub_role_id = None
        elif item_id.startswith("role_"):
            self.current_role_id = int(item_id.replace("role_", ""))
            self.current_sub_role_id = None
        else:
            self.current_sub_role_id = int(item_id.replace("sub_", ""))
            self.current_role_id = None

        self._load_tables()

    def _load_tables(self):
        self.types_id_to_name = {t[0]: t[1] for t in self.types_repo.get_all()}

        if self.sheet_types:
            self.types_data = self.types_repo.get_filtered(self.current_role_id, self.current_sub_role_id)
            types_rows = []
            for t in self.types_data:
                t_id, name, desc, rid, srid, freq, imp = t
                rname = self.roles_id_to_name.get(rid, "")
                srname = self.sub_roles_id_to_name.get(srid, "")
                types_rows.append([name, desc or "", rname, srname, freq, imp, t_id])

            types_rows = sort_sheet_data(types_rows, self.types_sort_col, self.types_sort_asc, numeric_cols=[4, 5, 6])
            self.sheet_types.set_sheet_data(types_rows, reset_col_positions=False)
        else:
            self.types_data = []

        if self.sheet_duties:
            self.duties_data = self.duties_repo.get_filtered(self.current_role_id, self.current_sub_role_id)
            duties_rows = []
            for d in self.duties_data:
                d_id, name, desc, ord_val, imp_val, tid, period, rid, srid = d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7], d[8]
                tname = self.types_id_to_name.get(tid, "")
                rname = self.roles_id_to_name.get(rid, "")
                srname = self.sub_roles_id_to_name.get(srid, "")
                duties_rows.append([ord_val, name, desc or "", tname, period, rname, srname, imp_val, d_id])

            duties_rows = sort_sheet_data(duties_rows, self.duties_sort_col, self.duties_sort_asc, numeric_cols=[0, 7, 8])
            self.sheet_duties.set_sheet_data(duties_rows, reset_col_positions=False)
        else:
            self.duties_data = []

    # ------------------------------------------------------------------
    # Обработчики inline-редактирования
    # ------------------------------------------------------------------
    def _on_type_cell_edited(self, event):
        row = event.row
        col = event.column

        if col in [2, 3, 6]:
            return

        type_id = self.sheet_types.get_cell_data(row, 6)
        t_data = next((t for t in self.types_data if t[0] == type_id), None)
        if not t_data:
            self.refresh_all()
            return

        name = self.sheet_types.get_cell_data(row, 0)
        if not name or not str(name).strip():
            messagebox.showwarning("Ошибка", "Название не может быть пустым")
            self.refresh_all()
            return

        desc = self.sheet_types.get_cell_data(row, 1)

        try:
            freq = int(self.sheet_types.get_cell_data(row, 4) or 1)
        except Exception:
            freq = 1
            self.sheet_types.set_cell_data(row, 4, freq)

        try:
            imp = int(self.sheet_types.get_cell_data(row, 5) or 1)
        except Exception:
            imp = 1
            self.sheet_types.set_cell_data(row, 5, imp)

        try:
            self.types_repo.update(type_id, name, desc or "", t_data[3], t_data[4], freq, imp)
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))

        self.refresh_all()

    def _on_duty_cell_edited(self, event):
        row = event.row
        col = event.column

        if col in [3, 4, 5, 6, 8]:
            return

        duty_id = self.sheet_duties.get_cell_data(row, 8)
        d_data = next((d for d in self.duties_data if d[0] == duty_id), None)
        if not d_data:
            self.refresh_all()
            return

        ord_val = self.sheet_duties.get_cell_data(row, 0)
        name = self.sheet_duties.get_cell_data(row, 1)
        desc = self.sheet_duties.get_cell_data(row, 2)
        imp_val = self.sheet_duties.get_cell_data(row, 7)

        if not name or not str(name).strip():
            messagebox.showwarning("Ошибка", "Название не может быть пустым")
            self.refresh_all()
            return

        try:
            execution_order = int(float(ord_val)) if str(ord_val).strip() else None
        except ValueError:
            execution_order = None

        try:
            importance = int(float(imp_val)) if str(imp_val).strip() else None
        except ValueError:
            importance = None

        try:
            self.duties_repo.update(duty_id, name, desc or "", d_data[5], d_data[6], d_data[7], d_data[8], execution_order, importance)
        except Exception as e:
            messagebox.showerror("Ошибка БД", str(e))

        self.refresh_all()

    def _on_types_column_select(self, event):
        col = getattr(event.selected, "column", None)
        if col is None:
            return
        if self.types_sort_col == col:
            self.types_sort_asc = not self.types_sort_asc
        else:
            self.types_sort_col = col
            self.types_sort_asc = True
        self.save_state()
        self._load_tables()

    def _on_duties_column_select(self, event):
        col = getattr(event.selected, "column", None)
        if col is None:
            return
        if self.duties_sort_col == col:
            self.duties_sort_asc = not self.duties_sort_asc
        else:
            self.duties_sort_col = col
            self.duties_sort_asc = True
        self.save_state()
        self._load_tables()

    # ------------------------------------------------------------------
    # CRUD: Добавление (через диалог)
    # ------------------------------------------------------------------
    def _open_add_type(self):
        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Новый тип активности")

        dialog.update_idletasks()
        parent = self.winfo_toplevel()
        dw, dh = 550, 590
        x = parent.winfo_rootx() + (parent.winfo_width() - dw) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - dh) // 2
        dialog.geometry(f"{dw}x{dh}+{max(x, 0)}+{max(y, 0)}")
        dialog.grab_set()

        # --- Роль (предзаполняется из текущего контекста) ---
        tk.Label(dialog, text="Роль:", anchor="w").pack(fill="x", padx=15, pady=(15, 0))
        roles_list = sorted(self.roles_repo.get_all(), key=lambda r: r[0])
        roles_display = {f"{r[0]}. {r[1]}": r[0] for r in roles_list}
        cb_role = ttk.Combobox(dialog, values=list(roles_display.keys()), state="readonly")
        cb_role.pack(fill="x", padx=15, pady=2)

        # --- Под-роль ---
        tk.Label(dialog, text="Под-роль:", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        cb_sub_role = ttk.Combobox(dialog, values=[], state="readonly")
        cb_sub_role.pack(fill="x", padx=15, pady=2)

        def _refresh_sub_roles(event=None):
            role_display = cb_role.get()
            if not role_display:
                cb_sub_role['values'] = []
                cb_sub_role.set("")
                return
            role_id = roles_display.get(role_display)
            if role_id is None:
                cb_sub_role['values'] = []
                cb_sub_role.set("")
                return
            subs = sorted(self.sub_roles_repo.get_by_parent(role_id), key=lambda sr: sr[0])
            cb_sub_role['values'] = [sr[1] for sr in subs]
            cb_sub_role.set("")

        cb_role.bind("<<ComboboxSelected>>", _refresh_sub_roles)

        # Предзаполнение из текущего выделения в дереве
        if self.current_sub_role_id is not None:
            parent_role_id = None
            parent_sub_name = self.sub_roles_id_to_name.get(self.current_sub_role_id, "")
            for r in roles_list:
                for sr in self.sub_roles_repo.get_by_parent(r[0]):
                    if sr[0] == self.current_sub_role_id:
                        parent_role_id = r[0]
                        break
                if parent_role_id is not None:
                    break
            if parent_role_id is not None:
                for display, rid in roles_display.items():
                    if rid == parent_role_id:
                        cb_role.set(display)
                        break
                _refresh_sub_roles()
                if parent_sub_name:
                    cb_sub_role.set(parent_sub_name)
        elif self.current_role_id is not None:
            for display, rid in roles_display.items():
                if rid == self.current_role_id:
                    cb_role.set(display)
                    break
            _refresh_sub_roles()

        # --- Название ---
        tk.Label(dialog, text="Название:", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        ent_name = tk.Entry(dialog)
        ent_name.pack(fill="x", padx=15, pady=2)

        # --- Описание ---
        tk.Label(dialog, text="Описание:", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        ent_desc = tk.Entry(dialog)
        ent_desc.pack(fill="x", padx=15, pady=2)

        # --- Частота ---
        tk.Label(dialog, text="Частота (1-10):", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        var_freq = tk.StringVar(value="1")
        tk.Spinbox(dialog, from_=1, to=10, textvariable=var_freq).pack(fill="x", padx=15, pady=2)

        # --- Важность ---
        tk.Label(dialog, text="Важность (1-10):", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        var_imp = tk.StringVar(value="1")
        tk.Spinbox(dialog, from_=1, to=10, textvariable=var_imp).pack(fill="x", padx=15, pady=2)

        def save():
            name = ent_name.get().strip()
            if not name:
                messagebox.showerror("Ошибка", "Название не может быть пустым", parent=dialog)
                return

            role_display = cb_role.get()
            role_id = roles_display.get(role_display) if role_display else None

            sub_name = cb_sub_role.get()
            sub_role_id = None
            if sub_name and role_id is not None:
                for sr in self.sub_roles_repo.get_by_parent(role_id):
                    if sr[1] == sub_name:
                        sub_role_id = sr[0]
                        break

            try:
                freq = int(var_freq.get())
                imp = int(var_imp.get())
            except ValueError:
                messagebox.showerror("Ошибка", "Частота и важность должны быть числами", parent=dialog)
                return

            try:
                self.types_repo.add(name, ent_desc.get().strip(), role_id, sub_role_id, freq, imp)
            except Exception as e:
                messagebox.showerror("Ошибка БД", str(e), parent=dialog)
                return

            dialog.destroy()
            self.refresh_all()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=15)
        tk.Button(frame_btns, text="Сохранить", command=save, width=12).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=dialog.destroy, width=12).pack(side="left", padx=5)

    def _open_add_duty(self):
        dialog = tk.Toplevel(self)
        dialog.transient(self.winfo_toplevel())
        dialog.title("Новая обязанность")

        dialog.update_idletasks()
        parent = self.winfo_toplevel()
        dw, dh = 550, 720
        x = parent.winfo_rootx() + (parent.winfo_width() - dw) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - dh) // 2
        dialog.geometry(f"{dw}x{dh}+{max(x, 0)}+{max(y, 0)}")
        dialog.grab_set()

        # Запоминаем тип, выделенный в таблице типов (для предзаполнения cb_type)
        prefilled_type_name = None
        if self.sheet_types is not None:
            sel = self.sheet_types.get_currently_selected()
            if sel is not None and getattr(sel, "row", None) is not None:
                prefilled_type_name = self.sheet_types.get_cell_data(sel.row, 0)

        # --- Роль ---
        tk.Label(dialog, text="Роль:", anchor="w").pack(fill="x", padx=15, pady=(15, 0))
        roles_list = sorted(self.roles_repo.get_all(), key=lambda r: r[0])
        roles_display = {f"{r[0]}. {r[1]}": r[0] for r in roles_list}
        cb_role = ttk.Combobox(dialog, values=list(roles_display.keys()), state="readonly")
        cb_role.pack(fill="x", padx=15, pady=2)

        # --- Под-роль ---
        tk.Label(dialog, text="Под-роль:", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        cb_sub_role = ttk.Combobox(dialog, values=[], state="readonly")
        cb_sub_role.pack(fill="x", padx=15, pady=2)

        # --- Тип активности (зависит от выбранной роли/подроли) ---
        tk.Label(dialog, text="Тип активности:", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        cb_type = ttk.Combobox(dialog, values=[], state="readonly")
        cb_type.pack(fill="x", padx=15, pady=2)

        state = {"types_map": {}}

        def _refresh_sub_roles():
            role_display = cb_role.get()
            if not role_display:
                cb_sub_role['values'] = []
                cb_sub_role.set("")
                return
            role_id = roles_display.get(role_display)
            if role_id is None:
                cb_sub_role['values'] = []
                cb_sub_role.set("")
                return
            subs = sorted(self.sub_roles_repo.get_by_parent(role_id), key=lambda sr: sr[0])
            cb_sub_role['values'] = [sr[1] for sr in subs]
            cb_sub_role.set("")

        def _refresh_types():
            role_display = cb_role.get()
            role_id = roles_display.get(role_display) if role_display else None
            sub_name = cb_sub_role.get()
            sub_role_id = None
            if sub_name and role_id is not None:
                for sr in self.sub_roles_repo.get_by_parent(role_id):
                    if sr[1] == sub_name:
                        sub_role_id = sr[0]
                        break
            relevant = self.types_repo.get_filtered(role_id, sub_role_id)
            state["types_map"] = {t[1]: t[0] for t in relevant}
            cb_type['values'] = list(state["types_map"].keys())
            cb_type.set("")

        def _on_role_change(event=None):
            _refresh_sub_roles()
            _refresh_types()

        cb_role.bind("<<ComboboxSelected>>", _on_role_change)
        cb_sub_role.bind("<<ComboboxSelected>>", lambda e: _refresh_types())

        # Предзаполнение из текущего выделения в дереве
        if self.current_sub_role_id is not None:
            parent_role_id = None
            parent_sub_name = self.sub_roles_id_to_name.get(self.current_sub_role_id, "")
            for r in roles_list:
                for sr in self.sub_roles_repo.get_by_parent(r[0]):
                    if sr[0] == self.current_sub_role_id:
                        parent_role_id = r[0]
                        break
                if parent_role_id is not None:
                    break
            if parent_role_id is not None:
                for display, rid in roles_display.items():
                    if rid == parent_role_id:
                        cb_role.set(display)
                        break
                _refresh_sub_roles()
                if parent_sub_name:
                    cb_sub_role.set(parent_sub_name)
        elif self.current_role_id is not None:
            for display, rid in roles_display.items():
                if rid == self.current_role_id:
                    cb_role.set(display)
                    break
            _refresh_sub_roles()

        _refresh_types()

        # Предзаполнение типа активности из выделения в таблице типов
        if prefilled_type_name and prefilled_type_name in state["types_map"]:
            cb_type.set(prefilled_type_name)

        # --- Название ---
        tk.Label(dialog, text="Название:", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        ent_name = tk.Entry(dialog)
        ent_name.pack(fill="x", padx=15, pady=2)

        # --- Описание ---
        tk.Label(dialog, text="Описание:", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        ent_desc = tk.Entry(dialog)
        ent_desc.pack(fill="x", padx=15, pady=2)

        # --- Порядок ---
        tk.Label(dialog, text="Порядок (пусто = NULL):", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        ent_ord = tk.Entry(dialog)
        ent_ord.pack(fill="x", padx=15, pady=2)

        # --- Важность ---
        tk.Label(dialog, text="Важность (пусто = NULL):", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        ent_imp = tk.Entry(dialog)
        ent_imp.pack(fill="x", padx=15, pady=2)

        # --- Период ---
        tk.Label(dialog, text="Период:", anchor="w").pack(fill="x", padx=15, pady=(10, 0))
        var_period = tk.StringVar(value="week")
        frm_per = tk.Frame(dialog)
        frm_per.pack(fill="x", padx=15, pady=2)
        tk.Radiobutton(frm_per, text="День", variable=var_period, value="day").pack(side="left")
        tk.Radiobutton(frm_per, text="Неделя", variable=var_period, value="week").pack(side="left")
        tk.Radiobutton(frm_per, text="Месяц", variable=var_period, value="month").pack(side="left")

        def save():
            name = ent_name.get().strip()
            if not name:
                messagebox.showerror("Ошибка", "Название не может быть пустым", parent=dialog)
                return

            type_name = cb_type.get()
            type_id = state["types_map"].get(type_name)
            if not type_id:
                messagebox.showerror("Ошибка", "Выберите тип активности", parent=dialog)
                return

            role_display = cb_role.get()
            role_id = roles_display.get(role_display) if role_display else None

            sub_name = cb_sub_role.get()
            sub_role_id = None
            if sub_name and role_id is not None:
                for sr in self.sub_roles_repo.get_by_parent(role_id):
                    if sr[1] == sub_name:
                        sub_role_id = sr[0]
                        break

            try:
                ord_val = int(float(ent_ord.get())) if ent_ord.get().strip() else None
            except ValueError:
                ord_val = None
            try:
                imp_val = int(float(ent_imp.get())) if ent_imp.get().strip() else None
            except ValueError:
                imp_val = None

            try:
                self.duties_repo.add(name, ent_desc.get().strip(), type_id, var_period.get(),
                                     role_id, sub_role_id, ord_val, imp_val)
            except Exception as e:
                messagebox.showerror("Ошибка БД", str(e), parent=dialog)
                return

            dialog.destroy()
            self.refresh_all()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=15)
        tk.Button(frame_btns, text="Сохранить", command=save, width=12).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=dialog.destroy, width=12).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Удаление
    # ------------------------------------------------------------------
    def _delete_item(self, item_type: str):
        if item_type == "type":
            sheet = self.sheet_types
            repo = self.types_repo
            id_col = 6
        else:
            sheet = self.sheet_duties
            repo = self.duties_repo
            id_col = 8

        if not sheet:
            return

        selected = sheet.get_currently_selected()
        row = getattr(selected, "row", None)
        if row is None:
            messagebox.showwarning("Внимание", "Выберите запись для удаления!")
            return

        item_id = sheet.get_cell_data(row, id_col)
        item_name = sheet.get_cell_data(row, 0 if item_type == "type" else 1)

        if not messagebox.askyesno("Подтверждение", f"Удалить '{item_name}'?"):
            return

        try:
            repo.delete(item_id)
            self.refresh_all()
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Ошибка удаления",
                f"Нельзя удалить «{item_name}»: запись используется в других таблицах.\n"
                f"Сначала удалите связанные данные."
            )
        except Exception as e:
            messagebox.showerror(
                "Ошибка БД",
                f"Не удалось удалить «{item_name}»:\n{e}"
            )