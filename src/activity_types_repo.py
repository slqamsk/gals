# src/activity_types_repo.py
# Репозиторий для работы со справочником типов активностей.

from .database import Database


class ActivityTypesRepository:
    # Управляет чтением и записью типов активностей.
    def __init__(self, db: Database):
        self.db = db

    # Возвращает список всех типов активностей (сортируем по частоте и важности).
    def get_all(self) -> list[tuple]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id, name, description, default_role_id, default_sub_role_id, usage_frequency, importance "
                "FROM activity_types ORDER BY usage_frequency DESC, importance DESC, name"
            ).fetchall()
        finally:
            conn.close()
        return rows

    # Возвращает типы активностей с фильтрацией по роли / подроли.
    def get_filtered(self, role_id: int | None = None, sub_role_id: int | None = None) -> list[tuple]:
        conn = self.db.connect()
        try:
            if sub_role_id is not None:
                rows = conn.execute(
                    "SELECT id, name, description, default_role_id, default_sub_role_id, usage_frequency, importance "
                    "FROM activity_types WHERE default_sub_role_id = :srid "
                    "ORDER BY usage_frequency DESC, importance DESC, name",
                    {"srid": sub_role_id}
                ).fetchall()
            elif role_id is not None:
                rows = conn.execute(
                    "SELECT id, name, description, default_role_id, default_sub_role_id, usage_frequency, importance "
                    "FROM activity_types "
                    "WHERE default_role_id = :rid OR default_sub_role_id IN (SELECT id FROM sub_roles WHERE parent_role_id = :rid) "
                    "ORDER BY usage_frequency DESC, importance DESC, name",
                    {"rid": role_id}
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, name, description, default_role_id, default_sub_role_id, usage_frequency, importance "
                    "FROM activity_types ORDER BY usage_frequency DESC, importance DESC, name"
                ).fetchall()
        finally:
            conn.close()
        return rows

    # Добавляет новый тип активности.
    def add(self, name: str, description: str, default_role_id: int | None, default_sub_role_id: int | None, freq: int, imp: int):
        conn = self.db.connect()
        try:
            conn.execute(
                "INSERT INTO activity_types (name, description, default_role_id, default_sub_role_id, usage_frequency, importance) "
                "VALUES (:name, :desc, :rid, :srid, :freq, :imp)",
                {"name": name, "desc": description, "rid": default_role_id, "srid": default_sub_role_id, "freq": freq, "imp": imp}
            )
            conn.commit()
        finally:
            conn.close()

    # Обновляет существующий тип активности.
    def update(self, type_id: int, name: str, description: str, default_role_id: int | None, default_sub_role_id: int | None, freq: int, imp: int):
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE activity_types SET name=:name, description=:desc, default_role_id=:rid, default_sub_role_id=:srid, usage_frequency=:freq, importance=:imp "
                "WHERE id=:id",
                {"id": type_id, "name": name, "desc": description, "rid": default_role_id, "srid": default_sub_role_id, "freq": freq, "imp": imp}
            )
            conn.commit()
        finally:
            conn.close()

    # Удаляет тип активности.
    def delete(self, type_id: int):
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM activity_types WHERE id = :id", {"id": type_id})
            conn.commit()
        finally:
            conn.close()