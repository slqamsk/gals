# src/app_ui.py
# Графический интерфейс приложения (главное окно).

import ctypes
import tkinter as tk
from tkinter import ttk

from . import datetime_utils
from .database import Database
from .app_config import AppConfig
from .preferences_repo import PreferencesRepository
from .roles_repo import RolesRepository
from .sub_roles_repo import SubRolesRepository

# Импортируем все вкладки
from .main_tab import MainTab
from .role_model_tab import RoleModelTab
from .role_tree_container import RoleTreeContainer
from .activities_tab import ActivitiesTab
from .measurements_tab import MeasurementsTab
from .questionnaires_tab import QuestionnairesTab
from .data_exchange_tab import DataExchangeTab
from .tools_tab import ToolsTab


# Отдельная запись в панели задач + разрешает свою иконку.
def setup_taskbar(app_id: str):
    shell32 = ctypes.WinDLL("shell32")
    shell32.SetCurrentProcessExplicitAppUserModelID(app_id)  # type: ignore


class App:
    # Главное окно приложения.
    def __init__(self, prefs_repo: PreferencesRepository, roles_repo: RolesRepository, sub_roles_repo: SubRolesRepository, config: AppConfig, db: Database):
        self.prefs_repo = prefs_repo
        self.roles_repo = roles_repo
        self.sub_roles_repo = sub_roles_repo
        self.config = config
        self.db = db

        self.prefs = self.prefs_repo.get_all()

        setup_taskbar(self.config.app_id)

        self.root = tk.Tk()
        self.root.title(self.prefs["window_title"])

        # Иконку ставим ДО того, как окно станет видимым.
        # Параметр default= применяет иконку ко всем будущим Toplevel-окнам
        # (диалогам, календарям, выпадающим спискам). Без него Tkinter
        # иногда сбрасывает иконку на дефолтное «перо».
        self.root.iconbitmap(
            default=str(self.config.assets_dir / self.config.icon_file)
        )

        self.root.geometry(
            f"{self.prefs['window_width']}x{self.prefs['window_height']}+{self.prefs['window_x']}+{self.prefs['window_y']}"
        )

        if self.prefs.get("is_maximized"):
            self.root.state("zoomed")

        self.root.minsize(
            self.prefs["window_min_width"], self.prefs["window_min_height"]
        )

        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

        # --- СОЗДАЁМ ВКЛАДКИ ВЕРХНЕГО УРОВНЯ ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        # 1. Вкладка "Главная"
        self.tab_main = MainTab(self.notebook, self.prefs_repo, self.on_exit)
        self.notebook.add(self.tab_main, text="Главная")

        # 2. Вкладка "Ролевая модель" (Вложенная)
        self.tab_role_model = RoleModelTab(self.notebook, self.roles_repo, self.sub_roles_repo, self.prefs_repo, self.db)
        self.notebook.add(self.tab_role_model, text="Ролевая модель")

        # 3. Вкладка "Дерево ролей" (Вложенная)
        self.tab_role_tree = RoleTreeContainer(self.notebook, self.db, self.roles_repo, self.sub_roles_repo, self.prefs_repo)
        self.notebook.add(self.tab_role_tree, text="Дерево ролей")

        # 4. Вкладка "Активности" (Вложенная)
        self.tab_activities = ActivitiesTab(self.notebook, self.db, self.roles_repo, self.sub_roles_repo, self.prefs_repo)
        self.notebook.add(self.tab_activities, text="Активности")

        # 5. Вкладка "Измерения" (Вложенная)
        self.tab_measurements = MeasurementsTab(self.notebook, self.db, self.prefs_repo)
        self.notebook.add(self.tab_measurements, text="Измерения")

        # 6. Вкладка "Опросы" (Вложенная)
        self.tab_questionnaires = QuestionnairesTab(
            self.notebook, self.db, self.roles_repo, self.sub_roles_repo, self.prefs_repo
        )
        self.notebook.add(self.tab_questionnaires, text="Опросы")

        # 7. Вкладка "Обмен данными"
        self.tab_exchange = DataExchangeTab(self.notebook, self.db)
        self.notebook.add(self.tab_exchange, text="Обмен данными")

        # 8. Вкладка "Инструменты"
        self.tab_tools = ToolsTab(self.notebook, self.db, self.prefs_repo)
        self.notebook.add(self.tab_tools, text="Инструменты")

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # --- ВОССТАНАВЛИВАЕМ ПОСЛЕДНЮЮ ОТКРЫТУЮ ВКЛАДКУ ---
        last_tab = self.prefs.get("last_tab", 0)
        if isinstance(last_tab, int) and 0 <= last_tab < len(self.notebook.tabs()):
            self.notebook.select(last_tab)

    # Автоматически обновляет данные при переключении на верхнюю вкладку.
    def _on_tab_changed(self, event):
        current_tab = self.notebook.nametowidget(self.notebook.select())
        if hasattr(current_tab, "refresh_all"):
            current_tab.refresh_all()

    # Обработчик закрытия окна: сохраняет геометрию и завершает приложение.
    def on_exit(self):
        is_maximized = (self.root.state() == "zoomed")
        self.prefs_repo.set("is_maximized", is_maximized)

        if not is_maximized:
            self.prefs_repo.set("window_width", self.root.winfo_width())
            self.prefs_repo.set("window_height", self.root.winfo_height())
            self.prefs_repo.set("window_x", self.root.winfo_x())
            self.prefs_repo.set("window_y", self.root.winfo_y())

        # Сохраняем состояние ВСЕХ внутренних таблиц
        self.tab_role_model.save_state()
        self.tab_role_tree.save_state()
        self.tab_activities.save_state()
        self.tab_measurements.save_state()
        self.tab_questionnaires.save_state()

        # Сохраняем индекс текущей верхней вкладки
        current_tab_idx = self.notebook.index("current")
        self.prefs_repo.set("last_tab", current_tab_idx)

        self.root.destroy()

    # Запускает цикл событий.
    def run(self):
        self.root.mainloop()


# Точка входа: собираем зависимости и запускаем.
def main():
    config = AppConfig()

    db = Database(config.db_file, config.migrations_dir)
    db.init_db()

    prefs_repo = PreferencesRepository(db)
    prefs_repo.init_defaults()

    # Инициализируем модуль времени глобально
    offset = prefs_repo.get("user_timezone_offset")
    datetime_utils.init_timezone(offset)

    roles_repo = RolesRepository(db)
    sub_roles_repo = SubRolesRepository(db)

    app = App(prefs_repo, roles_repo, sub_roles_repo, config, db)
    app.run()