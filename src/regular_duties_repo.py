# src/regular_duties_repo.py
# Репозиторий для работы со справочником регулярных обязанностей.

from .database import Database


class RegularDutiesRepository:
    # Управляет чтением и записью обязанностей в таблицу regular_duties.
    def __init__(self, db: Database):
        self.db = db

    def get_all(self) -> list[tuple]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id, name, description, execution_order, importance, activity_type_id, period_type, "
                "role_id, sub_role_id, created_at, updated_at "
                "FROM regular_duties ORDER BY execution_order ASC, name ASC"
            ).fetchall()
        finally:
            conn.close()
        return rows

    def get_filtered(self, role_id: int | None = None, sub_role_id: int | None = None) -> list[tuple]:
        conn = self.db.connect()
        try:
            if sub_role_id is not None:
                rows = conn.execute(
                    "SELECT id, name, description, execution_order, importance, activity_type_id, period_type, "
                    "role_id, sub_role_id, created_at, updated_at "
                    "FROM regular_duties WHERE sub_role_id = :srid "
                    "ORDER BY execution_order ASC, name ASC",
                    {"srid": sub_role_id}
                ).fetchall()
            elif role_id is not None:
                rows = conn.execute(
                    "SELECT id, name, description, execution_order, importance, activity_type_id, period_type, "
                    "role_id, sub_role_id, created_at, updated_at "
                    "FROM regular_duties "
                    "WHERE role_id = :rid OR sub_role_id IN (SELECT id FROM sub_roles WHERE parent_role_id = :rid) "
                    "ORDER BY execution_order ASC, name ASC",
                    {"rid": role_id}
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, name, description, execution_order, importance, activity_type_id, period_type, "
                    "role_id, sub_role_id, created_at, updated_at "
                    "FROM regular_duties ORDER BY execution_order ASC, name ASC"
                ).fetchall()
        finally:
            conn.close()
        return rows

    def get_by_id(self, duty_id: int) -> tuple | None:
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, name, description, execution_order, importance, activity_type_id, period_type, "
                "role_id, sub_role_id, created_at, updated_at "
                "FROM regular_duties WHERE id = :id",
                {"id": duty_id}
            ).fetchone()
        finally:
            conn.close()

    def get_by_activity_type(self, activity_type_id: int) -> list[tuple]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id, name, execution_order, importance, period_type, role_id, sub_role_id "
                "FROM regular_duties WHERE activity_type_id = :tid "
                "ORDER BY execution_order ASC, name ASC",
                {"tid": activity_type_id}
            ).fetchall()
        finally:
            conn.close()
        return rows

    def get_by_period_type(self, period_type: str) -> list[tuple]:
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id, name, execution_order, importance, activity_type_id, role_id, sub_role_id "
                "FROM regular_duties WHERE period_type = :pt "
                "ORDER BY execution_order ASC, name ASC",
                {"pt": period_type}
            ).fetchall()
        finally:
            conn.close()
        return rows

    def add(self, name: str, description: str, activity_type_id: int,
            period_type: str, role_id: int | None, sub_role_id: int | None,
            execution_order: int | None = None, importance: int | None = None):
        conn = self.db.connect()
        try:
            conn.execute(
                "INSERT INTO regular_duties "
                "(name, description, activity_type_id, period_type, role_id, sub_role_id, execution_order, importance) "
                "VALUES (:name, :desc, :type_id, :ptype, :role_id, :sub_id, :ord, :imp)",
                {
                    "name": name, "desc": description, "type_id": activity_type_id,
                    "ptype": period_type, "role_id": role_id, "sub_id": sub_role_id,
                    "ord": execution_order, "imp": importance
                }
            )
            conn.commit()
        finally:
            conn.close()

    def update(self, duty_id: int, name: str, description: str, activity_type_id: int,
               period_type: str, role_id: int | None, sub_role_id: int | None,
               execution_order: int | None = None, importance: int | None = None):
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE regular_duties SET "
                "name = :name, description = :desc, activity_type_id = :type_id, "
                "period_type = :ptype, role_id = :role_id, sub_role_id = :sub_id, "
                "execution_order = :ord, importance = :imp "
                "WHERE id = :id",
                {
                    "id": duty_id, "name": name, "desc": description, "type_id": activity_type_id,
                    "ptype": period_type, "role_id": role_id, "sub_id": sub_role_id,
                    "ord": execution_order, "imp": importance
                }
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, duty_id: int):
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM regular_duties WHERE id = :id", {"id": duty_id})
            conn.commit()
        finally:
            conn.close()