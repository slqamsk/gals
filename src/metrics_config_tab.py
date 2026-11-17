# src/metrics_config_tab.py
# Вкладка для настройки метрик (создание/удаление) для ролей и подролей.
#
# Состояние "свёрнуто/развёрнуто" дерева ролей хранится в preferences
# (roles_tree_state) и общее для всех вкладок с деревом ролей.

import tkinter as tk
from tkinter import ttk, messagebox
from .metrics_repo import MetricsRepository
from .roles_repo import RolesRepository
from .sub_roles_repo import SubRolesRepository
from .preferences_repo import PreferencesRepository
from .constants import MetricType
import sqlite3


class MetricsConfigTab(tk.Frame):
    def __init__(self, parent, metrics_repo: MetricsRepository, roles_repo: RolesRepository,
                 sub_roles_repo: SubRolesRepository, prefs_repo: PreferencesRepository):
        super().__init__(parent)
        self.metrics_repo = metrics_repo
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.prefs_repo = prefs_repo

        self.current_entity_type = None
        self.current_entity_id = None

        # --- Основной контейнер (PanedWindow) ---
        self.paned = tk.PanedWindow(self, orient="horizontal", sashwidth=5)
        self.paned.pack(fill="both", expand=True, padx=10, pady=10)

        # 1. Левая часть: Дерево и кнопки
        self.frame_tree = tk.Frame(self.paned)
        self.paned.add(self.frame_tree, stretch="always")

        # Панель кнопок над деревом
        frame_buttons = tk.Frame(self.frame_tree)
        frame_buttons.pack(fill="x", pady=5)

        self.btn_expand = tk.Button(frame_buttons, text="Развернуть всё", command=self.expand_all)
        self.btn_expand.pack(side="left", padx=2)

        self.btn_collapse = tk.Button(frame_buttons, text="Свернуть всё", command=self.collapse_all)
        self.btn_collapse.pack(side="left", padx=2)

        self.btn_refresh = tk.Button(frame_buttons, text="Обновить", command=self.refresh_all)
        self.btn_refresh.pack(side="left", padx=2)

        # Дерево с 5 колонками
        style = ttk.Style()
        style.configure("Metrics.Treeview", borderwidth=1, relief="solid", rowheight=25)
        style.configure("Metrics.Treeview.Heading", borderwidth=1, relief="solid", font=('Arial', 10, 'bold'))

        self.tree = ttk.Treeview(
            self.frame_tree,
            columns=("day", "week", "month", "manual"),
            selectmode="browse",
            style="Metrics.Treeview"
        )
        self.tree.heading("#0", text="Роль / Под-роль")
        self.tree.heading("day", text="День")
        self.tree.heading("week", text="Нед")
        self.tree.heading("month", text="Мес")
        self.tree.heading("manual", text="Руч")

        self.tree.column("#0", width=200)
        self.tree.column("day", width=50, anchor="center")
        self.tree.column("week", width=50, anchor="center")
        self.tree.column("month", width=50, anchor="center")
        self.tree.column("manual", width=50, anchor="center")

        # Настройка стилей (жирный для ролей, обычный для подролей)
        self.tree.tag_configure("role_node", font=("Arial", 11, "bold"))
        self.tree.tag_configure("sub_role_node", font=("Arial", 10, "normal"))

        self.tree.pack(fill="both", expand=True, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # Сохраняем состояние ролей при сворачивании/разворачивании
        self.tree.bind("<<TreeviewOpen>>", self._on_node_toggled)
        self.tree.bind("<<TreeviewClose>>", self._on_node_toggled)

        # 2. Правая часть: Настройки
        self.frame_settings = tk.Frame(self.paned)
        self.paned.add(self.frame_settings, stretch="always")

        self.lbl_title = tk.Label(self.frame_settings, text="Выберите роль или под-роль", font=("Arial", 11, "bold"))
        self.lbl_title.pack(pady=10)

        # Чекбоксы
        self.var_day = tk.BooleanVar()
        self.var_week = tk.BooleanVar()
        self.var_month = tk.BooleanVar()
        self.var_manual = tk.BooleanVar()

        tk.Checkbutton(self.frame_settings, text="Ежедневная (Day)", variable=self.var_day).pack(anchor="w", padx=20,
                                                                                                 pady=2)
        tk.Checkbutton(self.frame_settings, text="Еженедельная (Week)", variable=self.var_week).pack(anchor="w",
                                                                                                     padx=20, pady=2)
        tk.Checkbutton(self.frame_settings, text="Ежемесячная (Month)", variable=self.var_month).pack(anchor="w",
                                                                                                      padx=20, pady=2)
        tk.Checkbutton(self.frame_settings, text="Ручная (Manual)", variable=self.var_manual).pack(anchor="w", padx=20,
                                                                                                   pady=2)

        self.btn_save = tk.Button(self.frame_settings, text="Применить", command=self.save_metrics, state="disabled")
        self.btn_save.pack(pady=20)

        self.refresh_all()

    # ------------------------------------------------------------------
    # Состояние дерева
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
            iid = f"id_role_{role_id}"
            if self.tree.exists(iid):
                state[str(role_id)] = bool(self.tree.item(iid, "open"))
        self._save_state(state)

    # ------------------------------------------------------------------
    # Развернуть/свернуть всё
    # ------------------------------------------------------------------
    def expand_all(self):
        """Разворачивает все роли и записывает состояние (все True)."""
        roles = self.roles_repo.get_all()
        state = {str(r[0]): True for r in roles}
        self._save_state(state)
        if self.tree.exists("root"):
            self.tree.item("root", open=True)
        for item in self.tree.get_children("root"):
            if item.startswith("id_role_"):
                self.tree.item(item, open=True)

    def collapse_all(self):
        """Сворачивает все роли и записывает состояние (все False)."""
        roles = self.roles_repo.get_all()
        state = {str(r[0]): False for r in roles}
        self._save_state(state)
        if self.tree.exists("root"):
            self.tree.item("root", open=False)

    # ------------------------------------------------------------------
    # Обновление дерева
    # ------------------------------------------------------------------
    def refresh_all(self):
        # Сохраняем ID выбранной сущности (а не тип) для восстановления после перерисовки
        selected = self.tree.selection()
        selected_id_tag = None
        if selected:
            tags = self.tree.item(selected[0], "tags")
            selected_id_tag = next((t for t in tags if t.startswith("id_")), None)

        for item in self.tree.get_children():
            self.tree.delete(item)

        # Корень «Все роли»
        self.tree.insert(
            "", "end", iid="root", text="📁 Все роли",
            tags=("role_node",),
            open=True,
        )

        state = self._get_state()

        roles = sorted(self.roles_repo.get_all(), key=lambda r: r[0])
        all_metrics = self.metrics_repo.get_all_metrics()

        heavy_plus = "✚"

        for r in roles:
            role_id, name, desc, color = r[0], r[1], r[2], r[3]
            color = color or "#FFFFFF"

            r_day = heavy_plus if any(m["role_id"] == role_id and m["type"] == "day" for m in all_metrics) else ""
            r_week = heavy_plus if any(m["role_id"] == role_id and m["type"] == "week" for m in all_metrics) else ""
            r_month = heavy_plus if any(m["role_id"] == role_id and m["type"] == "month" for m in all_metrics) else ""
            r_manual = heavy_plus if any(m["role_id"] == role_id and m["type"] == "manual" for m in all_metrics) else ""

            role_text = f"{role_id}. {name}"
            tag_color = f"color_{role_id}"
            self.tree.tag_configure(tag_color, background=color)
            tag_id = f"id_role_{role_id}"

            is_open = state.get(str(role_id), True)

            r_node = self.tree.insert("root", "end", text=role_text, values=(r_day, r_week, r_month, r_manual),
                                      open=is_open,
                                      tags=("role_node", tag_color, tag_id))

            sub_roles = sorted(self.sub_roles_repo.get_by_parent(role_id), key=lambda sr: sr[0])
            for sr in sub_roles:
                sr_id, sr_name = sr[0], sr[1]

                s_day = heavy_plus if any(m["sub_role_id"] == sr_id and m["type"] == "day" for m in all_metrics) else ""
                s_week = heavy_plus if any(
                    m["sub_role_id"] == sr_id and m["type"] == "week" for m in all_metrics) else ""
                s_month = heavy_plus if any(
                    m["sub_role_id"] == sr_id and m["type"] == "month" for m in all_metrics) else ""
                s_manual = heavy_plus if any(
                    m["sub_role_id"] == sr_id and m["type"] == "manual" for m in all_metrics) else ""

                tag_sub_id = f"id_sub_role_{sr_id}"
                self.tree.insert(r_node, "end", text=sr_name, values=(s_day, s_week, s_month, s_manual),
                                 tags=("sub_role_node", tag_color, tag_sub_id))

        # Восстановление выделения по id_* тегу
        if selected_id_tag:
            for item in self.tree.get_children("root"):
                if selected_id_tag in self.tree.item(item, "tags"):
                    self.tree.selection_set(item)
                    break
                for child in self.tree.get_children(item):
                    if selected_id_tag in self.tree.item(child, "tags"):
                        self.tree.selection_set(child)
                        break

    def on_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        tags = self.tree.item(selected[0], "tags")
        id_tag = next((t for t in tags if t.startswith("id_")), None)
        if not id_tag:
            return

        if "role_node" in tags:
            self.current_entity_type = "role"
            self.current_entity_id = int(id_tag.replace("id_role_", ""))
        else:
            self.current_entity_type = "sub_role"
            self.current_entity_id = int(id_tag.replace("id_sub_role_", ""))

        entity_name = self.tree.item(selected[0], "text")
        self.lbl_title.config(text=f"Метрики для: {entity_name}")
        self.btn_save.config(state="normal")

        types = self.metrics_repo.get_metrics_for_entity(self.current_entity_type, self.current_entity_id)
        self.var_day.set(MetricType.DAY.value in types)
        self.var_week.set(MetricType.WEEK.value in types)
        self.var_month.set(MetricType.MONTH.value in types)
        self.var_manual.set(MetricType.MANUAL.value in types)

    def save_metrics(self):
        if not self.current_entity_id:
            return

        target = set()
        if self.var_day.get(): target.add(MetricType.DAY)
        if self.var_week.get(): target.add(MetricType.WEEK)
        if self.var_month.get(): target.add(MetricType.MONTH)
        if self.var_manual.get(): target.add(MetricType.MANUAL)

        current = self.metrics_repo.get_metrics_for_entity(self.current_entity_type, self.current_entity_id)
        current_enums = {MetricType(t) for t in current}

        to_add = target - current_enums
        to_remove = current_enums - target

        for m_type in to_add:
            try:
                self.metrics_repo.add_metric(self.current_entity_type, self.current_entity_id, m_type)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось добавить метрику:\n{e}")
                return

        for m_type in to_remove:
            try:
                self.metrics_repo.delete_metric(self.current_entity_type, self.current_entity_id, m_type)
            except sqlite3.IntegrityError:
                messagebox.showerror("Ошибка",
                                     f"Нельзя удалить метрику '{m_type.value}', так как к ней уже привязаны индикаторы.")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить метрику:\n{e}")

        self.refresh_all()