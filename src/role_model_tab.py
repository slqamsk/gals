# src/role_model_tab.py
# (Только роли, под-роли, индикаторы и графики)
# «Дерево ролей», «Метрики» и «Связи ролей» — в отдельной верхней вкладке
# «Дерево ролей» (см. role_tree_container.py).

import tkinter as tk
from tkinter import ttk
from .roles_repo import RolesRepository
from .sub_roles_repo import SubRolesRepository
from .preferences_repo import PreferencesRepository
from .chart_repo import ChartRepository
from .metrics_repo import MetricsRepository
from .indicator_repo import IndicatorRepository
from .activity_types_repo import ActivityTypesRepository
from .regular_duties_repo import RegularDutiesRepository
from .roles_excel_tab import RolesExcelTab
from .sub_roles_tab import SubRolesTab
from .indicator_config_tab import IndicatorConfigTab
from .chart_tab import ChartTab
from .chart_metrics_tab import ChartMetricsTab


class RoleModelTab(tk.Frame):
    def __init__(self, parent, roles_repo: RolesRepository, sub_roles_repo: SubRolesRepository,
                 prefs_repo: PreferencesRepository, db):
        super().__init__(parent)
        self.prefs_repo = prefs_repo

        # Инициализируем репозитории
        self.chart_repo = ChartRepository(db)
        self.metrics_repo = MetricsRepository(db)
        self.indicator_repo = IndicatorRepository(db)
        self.types_repo = ActivityTypesRepository(db)
        self.duties_repo = RegularDutiesRepository(db)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.tab_roles = RolesExcelTab(self.notebook, roles_repo, prefs_repo)
        self.notebook.add(self.tab_roles, text="Роли")

        self.tab_sub_roles = SubRolesTab(self.notebook, sub_roles_repo, roles_repo, prefs_repo)
        self.notebook.add(self.tab_sub_roles, text="Под-роли")

        self.tab_indicators = IndicatorConfigTab(
            self.notebook, self.indicator_repo, self.metrics_repo,
            self.types_repo, self.duties_repo, roles_repo, sub_roles_repo,
            prefs_repo
        )
        self.notebook.add(self.tab_indicators, text="Индикаторы")

        self.tab_chart = ChartTab(self.notebook, self.chart_repo, roles_repo, self.prefs_repo)
        self.notebook.add(self.tab_chart, text="График метрик")

        self.tab_chart_metrics = ChartMetricsTab(
            self.notebook, self.chart_repo, roles_repo, self.prefs_repo,
            self.indicator_repo, self.types_repo, self.duties_repo
        )
        self.notebook.add(self.tab_chart_metrics, text="График по периодам")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_sub_tab_changed)

        last_sub_tab = self.prefs_repo.get("last_sub_tab")
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
        elif hasattr(current_tab, "refresh_data"):
            current_tab.refresh_data()

    def _on_sub_tab_changed(self, event):
        self.refresh_all()

    def save_state(self):
        self.tab_roles.save_state()
        self.tab_sub_roles.save_state()
        current_idx = self.notebook.index("current")
        self.prefs_repo.set("last_sub_tab", current_idx)