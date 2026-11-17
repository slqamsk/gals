# src/data_exchange_tab.py
# Вкладка для импорта и экспорта данных (Excel / JSON).

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from .excel_service import ExcelService
from .json_service import JsonService
from .database import Database


class DataExchangeTab(tk.Frame):
    # Вкладка управления обменом данными.
    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.excel_service = ExcelService(db)
        self.json_service = JsonService(db)
        self.table_vars = {}

        # --- Заголовок ---
        tk.Label(self, text="Выберите таблицы для обмена:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=5)

        # --- Контейнер для чекбоксов ---
        self.frame_tables = tk.Frame(self)
        self.frame_tables.pack(fill="x", padx=20)
        self._load_tables()

        # --- Кнопки управления выбором ---
        frame_select = tk.Frame(self)
        frame_select.pack(fill="x", padx=20, pady=5)
        tk.Button(frame_select, text="Выбрать все", command=lambda: self._set_all_tables(True)).pack(side="left")
        tk.Button(frame_select, text="Очистить выбор", command=lambda: self._set_all_tables(False)).pack(side="left", padx=5)

        # --- Выбор формата ---
        frame_format = tk.Frame(self)
        frame_format.pack(fill="x", pady=10, padx=10)
        tk.Label(frame_format, text="Формат файла:").pack(side="left")

        self.format_var = tk.StringVar(value="xlsx")
        tk.Radiobutton(frame_format, text="Excel (.xlsx)", variable=self.format_var, value="xlsx").pack(side="left", padx=5)
        tk.Radiobutton(frame_format, text="JSON (.json)", variable=self.format_var, value="json").pack(side="left", padx=5)

        # --- Панель кнопок ---
        frame_buttons = tk.Frame(self)
        frame_buttons.pack(fill="x", pady=5, padx=10)

        self.btn_export = tk.Button(frame_buttons, text="Экспорт", command=self.on_export)
        self.btn_export.pack(side="left", padx=5)

        self.btn_import = tk.Button(frame_buttons, text="Импорт", command=self.on_import)
        self.btn_import.pack(side="left", padx=5)

        # --- Лог операций ---
        tk.Label(self, text="Лог операций:", font=("Arial", 9, "bold")).pack(anchor="w", padx=10)
        self.log_text = tk.Text(self, height=15, state="disabled", bg="#f0f0f0")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

    def _load_tables(self):
        for widget in self.frame_tables.winfo_children():
            widget.destroy()

        tables = self.db.get_table_names()
        for table in tables:
            var = tk.BooleanVar(value=False)
            chk = tk.Checkbutton(self.frame_tables, text=table, variable=var)
            chk.pack(anchor="w")
            self.table_vars[table] = var

    def _set_all_tables(self, state: bool):
        """Устанавливает или снимает галочки со всех таблиц."""
        for var in self.table_vars.values():
            var.set(state)

    def _log(self, message: str):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    def _get_selected_tables(self) -> list[str]:
        return [table for table, var in self.table_vars.items() if var.get()]

    def _get_service_and_ext(self):
        if self.format_var.get() == "json":
            return self.json_service, ".json", [("JSON files", "*.json")]
        return self.excel_service, ".xlsx", [("Excel files", "*.xlsx")]

    def on_export(self):
        self._clear_log()
        tables = self._get_selected_tables()
        if not tables:
            messagebox.showwarning("Внимание", "Выберите хотя бы одну таблицу!")
            return

        service, ext, filetypes = self._get_service_and_ext()

        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
        default_filename = f"gals-{timestamp}{ext}"

        filepath = filedialog.asksaveasfilename(
            initialfile=default_filename,
            defaultextension=ext,
            filetypes=filetypes,
            title="Сохранить как"
        )
        if not filepath:
            return

        try:
            service.export_tables(tables, filepath)
            self._log(f"УСПЕХ: Экспорт в {filepath}")
            messagebox.showinfo("Успех", "Экспорт завершен!")
        except Exception as e:
            self._log(f"ОШИБКА ЭКСПОРТА: {e}")
            messagebox.showerror("Ошибка", f"Не удалось экспортировать:\n{e}")

    def on_import(self):
        self._clear_log()
        tables = self._get_selected_tables()
        if not tables:
            messagebox.showwarning("Внимание", "Выберите хотя бы одну таблицу!")
            return

        service, ext, filetypes = self._get_service_and_ext()
        filepath = filedialog.askopenfilename(filetypes=filetypes, title="Выберите файл для импорта")
        if not filepath:
            return

        try:
            log_msgs = service.import_tables(tables, filepath)
            self._log("УСПЕХ: Импорт завершен.")
            for msg in log_msgs:
                self._log(msg)
            messagebox.showinfo("Успех", "Импорт завершен успешно!")
        except Exception as e:
            self._log(f"ОШИБКА ИМПОРТА (изменения отменены): {e}")
            messagebox.showerror("Ошибка импорта", f"Импорт отменен:\n{e}")