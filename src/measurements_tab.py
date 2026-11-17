# src/measurements_tab.py
# Контейнер верхней вкладки «Измерения».

import tkinter as tk
from tkinter import ttk

from .measurements_repo import MeasurementsRepository
from .measurements_input_tab import MeasurementsInputTab
from .measurements_history_tab import MeasurementsHistoryTab
from .measurements_settings_tab import MeasurementsSettingsTab


class MeasurementsTab(tk.Frame):
    def __init__(self, parent, db, prefs_repo):
        super().__init__(parent)
        self.db = db
        self.prefs_repo = prefs_repo
        self.repo = MeasurementsRepository(db)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self.tab_input = MeasurementsInputTab(self.notebook, self.repo, prefs_repo)
        self.notebook.add(self.tab_input, text="Ввод измерения")

        self.tab_history = MeasurementsHistoryTab(self.notebook, self.repo, prefs_repo)
        self.notebook.add(self.tab_history, text="История")

        self.tab_settings = MeasurementsSettingsTab(self.notebook, self.repo, prefs_repo)
        self.notebook.add(self.tab_settings, text="Настройки")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event):
        self.refresh_all()

    def refresh_all(self):
        current = self.notebook.nametowidget(self.notebook.select())
        if hasattr(current, "refresh_all"):
            current.refresh_all()
        elif hasattr(current, "refresh_table"):
            current.refresh_table()

    def save_state(self):
        for tab in (self.tab_input, self.tab_history, self.tab_settings):
            if hasattr(tab, "save_state"):
                try:
                    tab.save_state()
                except Exception:
                    pass