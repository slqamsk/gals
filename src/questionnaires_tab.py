# src/questionnaires_tab.py
# Контейнер верхней вкладки «Опросы».

import tkinter as tk
from tkinter import ttk

from .questions_repo import QuestionsRepository
from .questionnaires_mark_tab import QuestionnairesMarkTab
from .questionnaires_history_tab import QuestionnairesHistoryTab
from .questionnaires_settings_tab import QuestionnairesSettingsTab


class QuestionnairesTab(tk.Frame):
    def __init__(self, parent, db, roles_repo, sub_roles_repo, prefs_repo):
        super().__init__(parent)
        self.db = db
        self.prefs_repo = prefs_repo
        self.repo = QuestionsRepository(db)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.tab_mark = QuestionnairesMarkTab(
            self.notebook, self.repo, roles_repo, sub_roles_repo, prefs_repo
        )
        self.notebook.add(self.tab_mark, text="Отмечание")

        self.tab_history = QuestionnairesHistoryTab(
            self.notebook, self.repo, roles_repo, sub_roles_repo, prefs_repo
        )
        self.notebook.add(self.tab_history, text="История")

        self.tab_settings = QuestionnairesSettingsTab(
            self.notebook, self.repo, roles_repo, sub_roles_repo, prefs_repo
        )
        self.notebook.add(self.tab_settings, text="Настройка")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event):
        self.refresh_all()

    def refresh_all(self):
        cur = self.notebook.nametowidget(self.notebook.select())
        if hasattr(cur, "refresh_all"):
            cur.refresh_all()

    def save_state(self):
        for tab in (self.tab_mark, self.tab_history, self.tab_settings):
            if hasattr(tab, "save_state"):
                try:
                    tab.save_state()
                except Exception:
                    pass