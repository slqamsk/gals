# src/app_config.py
# Класс конфигурации приложения.
# Хранит пути к файлам, папкам и системные константы.

from pathlib import Path


class AppConfig:
    # Хранит пути к файлам и папкам проекта, а также системные константы.
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent  # корень проекта (gals/)
        self.assets_dir = self.root_dir / "assets"  # путь к папке с ресурсами
        self.migrations_dir = self.root_dir / "migrations"  # путь к папке с миграциями
        self.db_file = self.root_dir / "data" / "gals.db"  # абсолютный путь к файлу БД

        # Системные константы приложения
        self.app_id = "slqamsk.gals"  # ID для панели задач Windows
        self.icon_file = "icon.ico"  # имя файла иконки в папке assets