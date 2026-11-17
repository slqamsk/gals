# src/database.py
# Класс для работы с инфраструктурой SQLite: подключение и миграции.
#
# Каждая миграция применяется атомарно: один скрипт = одна транзакция,
# вместе с PRAGMA user_version. Падение в середине откатывает миграцию
# целиком, версия не сдвигается.
#
# Бэкап БД код НЕ делает: перед применением новых миграций пользователь
# сам копирует файл data/gals.db.
import sqlite3
from pathlib import Path


class Database:
    # Управляет подключением к БД и миграциями.
    def __init__(self, db_file: Path, migrations_dir: Path):
        self.db_file = db_file  # сохраняем путь к файлу БД
        self.migrations_dir = migrations_dir  # сохраняем путь к папке миграций

    # Открывает соединение, создавая папку data/ при необходимости.
    def connect(self) -> sqlite3.Connection:
        self.db_file.parent.mkdir(parents=True, exist_ok=True)  # создаём папку для БД
        conn = sqlite3.connect(self.db_file)  # создаём соединение
        conn.execute("PRAGMA foreign_keys = ON")  # внешние ключи (для ON DELETE RESTRICT)
        return conn

    # Возвращает список всех пользовательских таблиц в БД.
    def get_table_names(self) -> list[str]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
            return [row[0] for row in rows]
        finally:
            conn.close()

    # Вспомогательная статическая функция для сортировки путей.
    @staticmethod
    def _get_name(path: Path) -> str:
        return path.name

    # Возвращает все .sql-миграции, отсортированные по имени.
    def _migration_files(self) -> list[Path]:
        return sorted(self.migrations_dir.glob("*.sql"), key=self._get_name)

    # Применяет все миграции с номером > текущего user_version.
    def _apply_pending(self, conn: sqlite3.Connection):
        current = conn.execute("PRAGMA user_version").fetchone()[0]

        pending = []
        for path in self._migration_files():
            number = int(path.name.split("_", 1)[0])
            if number > current:
                pending.append((number, path))

        if not pending:
            return

        # PRAGMA foreign_keys не работает внутри транзакции, поэтому
        # выключаем FK на соединении ДО скриптов и включаем ПОСЛЕ.
        # Миграции 008 и 013 делают то же самое у себя внутри — там эти
        # PRAGMA станут пустыми операциями, что нам и нужно.
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            for number, path in pending:
                sql = path.read_text(encoding="utf-8")
                script = f"BEGIN;\n{sql}\nPRAGMA user_version = {number};\nCOMMIT;"
                try:
                    conn.executescript(script)
                except Exception as e:
                    conn.rollback()
                    raise RuntimeError(
                        f"Миграция '{path.name}' не применена и отменена целиком. "
                        f"База осталась на версии {current}. Причина: {e}"
                    ) from e
                current = number
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

    # Создаёт/обновляет структуру БД (применяет миграции).
    def init_db(self):
        conn = self.connect()
        try:
            self._apply_pending(conn)
        finally:
            conn.close()