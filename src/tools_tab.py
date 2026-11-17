# src/tools_tab.py
# Вкладка "Инструменты" для служебных операций и тестов.

import tkinter as tk
from tkinter import ttk
from .tools_debt_tab import ToolsDebtTab
from .tools_debug_tab import ToolsDebugTab
from .tools_web_events_tab import ToolsWebEventsTab


class ToolsTab(tk.Frame):
    # Контейнер для служебных подвкладок.
    def __init__(self, parent, db, prefs_repo):
        super().__init__(parent)
        self.db = db
        self.prefs_repo = prefs_repo

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        # 1. Подвкладка "Техдолг"
        self.tab_debt = ToolsDebtTab(self.notebook)
        self.notebook.add(self.tab_debt, text="Техдолг")

        # 2. Подвкладка "Служебные операции"
        self.tab_debug = ToolsDebugTab(self.notebook, db)
        self.notebook.add(self.tab_debug, text="Служебные операции")

        # 3. Подвкладка "Web-события"
        self.tab_web_events = ToolsWebEventsTab(self.notebook, db, prefs_repo)
        self.notebook.add(self.tab_web_events, text="Web-события")