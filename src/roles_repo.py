# src/roles_repo.py
# Класс-репозиторий для работы с ролями в БД.

from .database import Database


class RolesRepository:
    # Управляет чтением и записью ролей в таблицу roles.
    def __init__(self, db: Database):
        self.db = db

    # Возвращает список всех ролей из БД.
    def get_all(self) -> list[tuple]:
        conn = self.db.connect()
        try:
            rows = conn.execute("SELECT id, name, description, color FROM roles ORDER BY name").fetchall()
        finally:
            conn.close()
        return rows

    # Добавляет новую роль в БД.
    def add(self, name: str, description: str, color: str = "#FFFFFF"):
        conn = self.db.connect()
        try:
            conn.execute(
                "INSERT INTO roles(name, description, color) VALUES(?, ?, ?)",
                (name, description, color),
            )
            conn.commit()
        finally:
            conn.close()

    # Обновляет существующую роль в БД.
    def update(self, role_id: int, name: str, description: str, color: str):
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE roles SET name = ?, description = ?, color = ? WHERE id = ?",
                (name, description, color, role_id),
            )
            conn.commit()
        finally:
            conn.close()

    # Удаляет роль по её ID.
    def delete(self, role_id: int):
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM roles WHERE id = ?", (role_id,))
            conn.commit()
        finally:
            conn.close()