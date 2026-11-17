# src/sub_roles_repo.py
# Класс-репозиторий для работы с под-ролями в БД.

from .database import Database


class SubRolesRepository:
    # Управляет чтением и записью под-ролей в таблицу sub_roles.
    def __init__(self, db: Database):
        self.db = db  # сохраняем ссылку на базу данных

    # Возвращает список под-ролей для конкретной роли.
    def get_by_parent(self, parent_id: int) -> list[tuple]:
        conn = self.db.connect()
        try:
            # выбираем под-роли только для указанного родителя
            rows = conn.execute(
                "SELECT id, name, description FROM sub_roles WHERE parent_role_id = ? ORDER BY name",
                (parent_id,)
            ).fetchall()
        finally:
            conn.close()
        return rows

    # Добавляет новую под-роль.
    def add(self, name: str, description: str, parent_id: int):
        conn = self.db.connect()
        try:
            conn.execute(
                "INSERT INTO sub_roles(name, description, parent_role_id) VALUES(?, ?, ?)",
                (name, description, parent_id),
            )
            conn.commit()
        finally:
            conn.close()

    # Обновляет под-роль.
    def update(self, sub_role_id: int, name: str, description: str):
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE sub_roles SET name = ?, description = ? WHERE id = ?",
                (name, description, sub_role_id),
            )
            conn.commit()
        finally:
            conn.close()

    # Удаляет под-роль.
    def delete(self, sub_role_id: int):
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM sub_roles WHERE id = ?", (sub_role_id,))
            conn.commit()
        finally:
            conn.close()