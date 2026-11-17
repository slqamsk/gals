# src/activities_tab.py
# Главная вкладка "Активности" с внутренними подвкладками.

import tkinter as tk
from tkinter import ttk
from .activities_repo import ActivitiesRepository
from .activity_types_repo import ActivityTypesRepository
from .regular_duties_repo import RegularDutiesRepository
from .roles_repo import RolesRepository
from .sub_roles_repo import SubRolesRepository
from .preferences_repo import PreferencesRepository
from .manual_activities_tab import ManualActivitiesTab
from .activity_types_tab import ActivityTypesTab
from .regular_duties_tab import RegularDutiesTab
from .regular_duty_marks_tab import RegularDutyMarksTab


class ActivitiesTab(tk.Frame):
    # Контейнер для всего, что связано с активностями.
    def __init__(self, parent, db, roles_repo, sub_roles_repo, prefs_repo):
        super().__init__(parent)
        self.prefs_repo = prefs_repo

        # Инициализируем репозитории
        self.activities_repo = ActivitiesRepository(db)
        self.types_repo = ActivityTypesRepository(db)
        self.duties_repo = RegularDutiesRepository(db)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # 1. Вкладка "Ручная работа"
        self.tab_manual = ManualActivitiesTab(
            self.notebook, self.activities_repo, self.types_repo,
            roles_repo, sub_roles_repo, prefs_repo
        )
        self.notebook.add(self.tab_manual, text="Ручная работа с активностями")

        # 2. Вкладка "Типы активностей"
        self.tab_types = ActivityTypesTab(
            self.notebook, self.types_repo, roles_repo, sub_roles_repo, prefs_repo
        )
        self.notebook.add(self.tab_types, text="Типы активностей")

        # 3. Вкладка "Обязанности"
        self.tab_duties = RegularDutiesTab(
            self.notebook, self.duties_repo, self.types_repo,
            roles_repo, sub_roles_repo, prefs_repo
        )
        self.notebook.add(self.tab_duties, text="Обязанности")

        # 4. Вкладка "Выполнение обязанностей"
        self.tab_marks = RegularDutyMarksTab(
            self.notebook,
            self.activities_repo, self.types_repo, self.duties_repo,
            roles_repo, sub_roles_repo, prefs_repo
        )
        self.notebook.add(self.tab_marks, text="Выполнение обязанностей")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_sub_tab_changed)

        last_sub_tab = self.prefs_repo.get("last_activities_sub_tab")
        if isinstance(last_sub_tab, int) and 0 <= last_sub_tab < len(self.notebook.tabs()):
            self.notebook.select(last_sub_tab)

    def refresh_all(self):
        current_tab = self.notebook.nametowidget(self.notebook.select())
        if hasattr(current_tab, "refresh_all"):
            current_tab.refresh_all()
        elif hasattr(current_tab, "refresh_table"):
            current_tab.refresh_table()

    def _on_sub_tab_changed(self, event):
        self.refresh_all()

    def save_state(self):
        self.tab_types.save_state()
        self.tab_manual.save_state()
        self.tab_duties.save_state()
        self.tab_marks.save_state()

        current_idx = self.notebook.index("current")
        self.prefs_repo.set("last_activities_sub_tab", current_idx)