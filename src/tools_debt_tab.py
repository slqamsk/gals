# src/tools_debt_tab.py
# Вкладка "Техдолг" (внутри Инструментов).
# Отображает содержимое roadmap.md.

import tkinter as tk
from pathlib import Path


class ToolsDebtTab(tk.Frame):
    # Вкладка для отображения технического долга (из roadmap.md).
    def __init__(self, parent):
        super().__init__(parent)

        # Вычисляем путь к roadmap.md (он лежит в корне проекта, на уровень выше src)
        root_dir = Path(__file__).parent.parent
        roadmap_path = root_dir / "docs/roadmap.md"

        try:
            with open(roadmap_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            content = f"Не удалось загрузить roadmap.md:\n{e}\n\nОжидаемый путь: {roadmap_path}"

        # Text для скроллинга. Consolas делает markdown читаемее.
        text_widget = tk.Text(
            self,
            wrap="word",
            font=("Consolas", 10),
            bg="#f9f9f9",
            padx=10,
            pady=10
        )
        text_widget.insert("1.0", content)
        text_widget.config(state="disabled")  # только для чтения
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)