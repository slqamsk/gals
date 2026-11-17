# src/role_tree_container.py
# Верхняя вкладка «Дерево ролей».
# Содержит 3 подвкладки:
#   - Дерево ролей  (просмотр иерархии)
#   - Метрики       (настройка периодов для роли/подроли)
#   - Связи ролей   (3-панельный просмотр/редактирование)
# Состояние «свёрнуто/развёрнуто» деревьев хранится в preferences
# (roles_tree_state) и общее для всех вкладок с деревом ролей.

import tkinter as tk
from tkinter import ttk

from .metrics_repo import MetricsRepository
from .activity_types_repo import ActivityTypesRepository
from .regular_duties_repo import RegularDutiesRepository
from .tree_tab import TreeRolesTab
from .metrics_config_tab import MetricsConfigTab
from .role_links_tab import RoleLinksTab


class RoleTreeContainer(tk.Frame):
    def __init__(self, parent, db, roles_repo, sub_roles_repo, prefs_repo):
        super().__init__(parent)
        self.prefs_repo = prefs_repo

        self.metrics_repo = MetricsRepository(db)
        self.types_repo = ActivityTypesRepository(db)
        self.duties_repo = RegularDutiesRepository(db)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # 1. Подвкладка «Дерево ролей» (просмотр)
        self.tab_tree = TreeRolesTab(self.notebook, roles_repo, sub_roles_repo, prefs_repo)
        self.notebook.add(self.tab_tree, text="Дерево ролей")

        # 2. Подвкладка «Метрики»
        self.tab_metrics = MetricsConfigTab(
            self.notebook, self.metrics_repo, roles_repo, sub_roles_repo, prefs_repo
        )
        self.notebook.add(self.tab_metrics, text="Метрики")

        # 3. Подвкладка «Связи ролей»
        self.tab_links = RoleLinksTab(
            self.notebook, roles_repo, sub_roles_repo,
            self.types_repo, self.duties_repo, prefs_repo
        )
        self.notebook.add(self.tab_links, text="Связи ролей")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_sub_tab_changed)

        last_sub_tab = self.prefs_repo.get("last_role_tree_sub_tab")
        if isinstance(last_sub_tab, int) and 0 <= last_sub_tab < len(self.notebook.tabs()):
            self.notebook.select(last_sub_tab)

    def refresh_all(self):
        current_tab = self.notebook.nametowidget(self.notebook.select())
        if hasattr(current_tab, "refresh_all"):
            current_tab.refresh_all()
        elif hasattr(current_tab, "refresh_table"):
            current_tab.refresh_table()
        elif hasattr(current_tab, "refresh_tree"):
            current_tab.refresh_tree()

    def _on_sub_tab_changed(self, event):
        self.refresh_all()

    def save_state(self):
        self.tab_links.save_state()
        current_idx = self.notebook.index("current")
        self.prefs_repo.set("last_role_tree_sub_tab", current_idx)