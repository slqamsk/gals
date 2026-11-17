# src/main_tab.py
# Главная вкладка приложения.

import tkinter as tk


class MainTab(tk.Frame):
    # Главная вкладка приложения.
    def __init__(self, parent, prefs_repo, on_exit_callback):
        super().__init__(parent)
        self.prefs_repo = prefs_repo
        self.prefs = self.prefs_repo.get_all()

        # Текст-заглушка
        self.label = tk.Label(
            self,
            text=self.prefs["placeholder_text"],
            font=(
                self.prefs["placeholder_font_family"],
                self.prefs["placeholder_font_size"],
            ),
        )
        self.label.pack(expand=True, pady=20)

        # Кнопка выхода
        self.button = tk.Button(
            self,
            text=self.prefs["button_text"],
            width=self.prefs["button_width"],
            command=on_exit_callback,
        )
        self.button.pack(pady=20)