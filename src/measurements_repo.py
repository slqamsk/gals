# src/measurements_repo.py
# Репозиторий для подсистемы измерений (EAV):
# units, measurement_types, measurement_components,
# measurement_sessions, measurement_values.
#
# Один репозиторий на 5 таблиц — потому что это одна подсистема,
# и запросы между таблицами пересекаются (сеанс + значения — одна транзакция).
#
# Подход к единицам: единица на компоненте (не на значении). Без конверсии.

from . import datetime_utils
from .database import Database


class MeasurementsRepository:
    def __init__(self, db: Database):
        self.db = db

    # =========================================================================
    # ЕДИНИЦЫ (units)
    # =========================================================================
    def get_all_units(self) -> list[tuple]:
        """(id, display_name, full_name, description). Сортировка по display_name."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, display_name, full_name, description "
                "FROM units ORDER BY display_name"
            ).fetchall()
        finally:
            conn.close()

    def get_unit_by_id(self, unit_id: int) -> tuple | None:
        """(id, display_name, full_name, description) или None."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, display_name, full_name, description "
                "FROM units WHERE id = :id",
                {"id": unit_id}
            ).fetchone()
        finally:
            conn.close()

    def add_unit(self, display_name: str, full_name: str, description: str | None):
        conn = self.db.connect()
        try:
            now = datetime_utils.get_now_iso()
            conn.execute(
                "INSERT INTO units (display_name, full_name, description, created_at) "
                "VALUES (:dn, :fn, :desc, :now)",
                {"dn": display_name, "fn": full_name, "desc": description, "now": now}
            )
            conn.commit()
        finally:
            conn.close()

    def update_unit(self, unit_id: int, display_name: str, full_name: str, description: str | None):
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE units SET display_name = :dn, full_name = :fn, description = :desc "
                "WHERE id = :id",
                {"id": unit_id, "dn": display_name, "fn": full_name, "desc": description}
            )
            conn.commit()
        finally:
            conn.close()

    def delete_unit(self, unit_id: int):
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM units WHERE id = :id", {"id": unit_id})
            conn.commit()
        finally:
            conn.close()

    def get_units_usage(self, unit_id: int) -> list[tuple]:
        """Где используется единица: [(component_name, type_name), ...].
        Для сообщения об ошибке при удалении."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT c.name, mt.name "
                "FROM measurement_components c "
                "JOIN measurement_types mt ON c.measurement_type_id = mt.id "
                "WHERE c.unit_id = :uid",
                {"uid": unit_id}
            ).fetchall()
        finally:
            conn.close()

    # =========================================================================
    # ТИПЫ ИЗМЕРЕНИЙ (measurement_types)
    # =========================================================================
    def get_all_types(self) -> list[tuple]:
        """(id, name, description). Сортировка по name."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, name, description "
                "FROM measurement_types ORDER BY name"
            ).fetchall()
        finally:
            conn.close()

    def get_type_by_id(self, type_id: int) -> tuple | None:
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, name, description FROM measurement_types WHERE id = :id",
                {"id": type_id}
            ).fetchone()
        finally:
            conn.close()

    def add_type(self, name: str, description: str | None):
        conn = self.db.connect()
        try:
            now = datetime_utils.get_now_iso()
            conn.execute(
                "INSERT INTO measurement_types (name, description, created_at) "
                "VALUES (:name, :desc, :now)",
                {"name": name, "desc": description, "now": now}
            )
            conn.commit()
        finally:
            conn.close()

    def update_type(self, type_id: int, name: str, description: str | None):
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE measurement_types SET name = :name, description = :desc "
                "WHERE id = :id",
                {"id": type_id, "name": name, "desc": description}
            )
            conn.commit()
        finally:
            conn.close()

    def delete_type(self, type_id: int):
        conn = self.db.connect()
        try:
            conn.execute(
                "DELETE FROM measurement_types WHERE id = :id",
                {"id": type_id}
            )
            conn.commit()
        finally:
            conn.close()

    def get_type_usage(self, type_id: int) -> tuple[int, int]:
        """(components_count, sessions_count) — для сообщения при удалении."""
        conn = self.db.connect()
        try:
            comps = conn.execute(
                "SELECT COUNT(*) FROM measurement_components WHERE measurement_type_id = :tid",
                {"tid": type_id}
            ).fetchone()[0]
            sessions = conn.execute(
                "SELECT COUNT(*) FROM measurement_sessions WHERE measurement_type_id = :tid",
                {"tid": type_id}
            ).fetchone()[0]
            return comps, sessions
        finally:
            conn.close()

    # =========================================================================
    # КОМПОНЕНТЫ ТИПОВ (measurement_components)
    # =========================================================================
    def get_components_for_type(self, type_id: int) -> list[tuple]:
        """(component_id, name, unit_id, unit_display, display_order, is_required).
        Сортировка по display_order, id."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT c.id, c.name, c.unit_id, u.display_name, c.display_order, c.is_required "
                "FROM measurement_components c "
                "JOIN units u ON c.unit_id = u.id "
                "WHERE c.measurement_type_id = :tid "
                "ORDER BY c.display_order, c.id",
                {"tid": type_id}
            ).fetchall()
        finally:
            conn.close()

    def get_components_full_for_type(self, type_id: int) -> list[dict]:
        """Для формы ввода и истории: [{id, name, unit_id, unit_display, display_order, is_required}]."""
        rows = self.get_components_for_type(type_id)
        return [
            {
                "id": r[0],
                "name": r[1],
                "unit_id": r[2],
                "unit_display": r[3],
                "display_order": r[4],
                "is_required": bool(r[5]),
            }
            for r in rows
        ]

    def get_component_by_id(self, component_id: int) -> tuple | None:
        """(id, measurement_type_id, name, unit_id, display_order, is_required)."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT id, measurement_type_id, name, unit_id, display_order, is_required "
                "FROM measurement_components WHERE id = :id",
                {"id": component_id}
            ).fetchone()
        finally:
            conn.close()

    def add_component(self, measurement_type_id: int, name: str, unit_id: int,
                      display_order: int = 1, is_required: int = 1):
        conn = self.db.connect()
        try:
            now = datetime_utils.get_now_iso()
            conn.execute(
                "INSERT INTO measurement_components "
                "(measurement_type_id, name, unit_id, display_order, is_required, created_at) "
                "VALUES (:tid, :name, :uid, :ord, :req, :now)",
                {"tid": measurement_type_id, "name": name, "uid": unit_id,
                 "ord": display_order, "req": is_required, "now": now}
            )
            conn.commit()
        finally:
            conn.close()

    def update_component(self, component_id: int, name: str, unit_id: int,
                         display_order: int, is_required: int):
        conn = self.db.connect()
        try:
            conn.execute(
                "UPDATE measurement_components "
                "SET name = :name, unit_id = :uid, display_order = :ord, is_required = :req "
                "WHERE id = :id",
                {"id": component_id, "name": name, "uid": unit_id,
                 "ord": display_order, "req": is_required}
            )
            conn.commit()
        finally:
            conn.close()

    def delete_component(self, component_id: int):
        conn = self.db.connect()
        try:
            conn.execute(
                "DELETE FROM measurement_components WHERE id = :id",
                {"id": component_id}
            )
            conn.commit()
        finally:
            conn.close()

    def get_component_usage(self, component_id: int) -> int:
        """Сколько значений ссылается на компонент (для сообщения при удалении)."""
        conn = self.db.connect()
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM measurement_values WHERE measurement_component_id = :cid",
                {"cid": component_id}
            ).fetchone()[0]
        finally:
            conn.close()

    # =========================================================================
    # СЕАНСЫ + ЗНАЧЕНИЯ (measurement_sessions + measurement_values)
    # =========================================================================

    def add_session(self, measurement_type_id: int, measured_at: str,
                    notes: str | None, values: dict[int, float]) -> int:
        """Создаёт сеанс + значения одной транзакцией.

        Args:
            measurement_type_id: ID типа.
            measured_at: ISO 8601 (секунды обнуляются здесь).
            notes: комментарий к сеансу.
            values: {component_id: value}. Должны быть ВСЕ обязательные компоненты.

        Returns:
            session_id.

        Raises:
            ValueError — если не все обязательные компоненты заполнены,
                         или если передан компонент чужого типа.
        """
        # Обнуляем секунды (MVP: минутная точность)
        measured_at = datetime_utils.to_minute_iso(measured_at)

        # Проверка: все обязательные компоненты заполнены
        components = self.get_components_for_type(measurement_type_id)
        if not components:
            raise ValueError(
                f"У типа измерения id={measurement_type_id} нет компонентов. "
                f"Сначала создайте компоненты в настройках."
            )

        required_ids = {c[0] for c in components if c[5]}
        all_ids = {c[0] for c in components}

        provided_ids = set(values.keys())
        missing = required_ids - provided_ids
        if missing:
            names = [c[1] for c in components if c[0] in missing]
            raise ValueError(
                "Не заполнены обязательные компоненты: " + ", ".join(names)
            )
        extra = provided_ids - all_ids
        if extra:
            raise ValueError(
                f"Переданы значения для компонентов чужого типа: {extra}"
            )

        conn = self.db.connect()
        try:
            conn.execute("BEGIN")
            now = datetime_utils.get_now_iso()
            cur = conn.execute(
                "INSERT INTO measurement_sessions "
                "(measurement_type_id, measured_at, notes, created_at) "
                "VALUES (:tid, :at, :notes, :now)",
                {"tid": measurement_type_id, "at": measured_at,
                 "notes": notes, "now": now}
            )
            session_id = cur.lastrowid

            for comp_id, val in values.items():
                conn.execute(
                    "INSERT INTO measurement_values "
                    "(measurement_session_id, measurement_component_id, value, created_at) "
                    "VALUES (:sid, :cid, :val, :now)",
                    {"sid": session_id, "cid": comp_id, "val": float(val), "now": now}
                )

            conn.commit()
            return session_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def update_session(self, session_id: int, measured_at: str,
                       notes: str | None, values: dict[int, float]):
        """Обновляет сеанс: метаданные + полный набор значений (delete + insert).

        Raises:
            ValueError — если не все обязательные компоненты заполнены.
        """
        measured_at = datetime_utils.to_minute_iso(measured_at)

        conn = self.db.connect()
        try:
            # Получаем тип сеанса
            row = conn.execute(
                "SELECT measurement_type_id FROM measurement_sessions WHERE id = :sid",
                {"sid": session_id}
            ).fetchone()
            if not row:
                raise ValueError(f"Сеанс id={session_id} не найден")
            type_id = row[0]

            components = self.get_components_for_type(type_id)
            required_ids = {c[0] for c in components if c[5]}
            missing = required_ids - set(values.keys())
            if missing:
                names = [c[1] for c in components if c[0] in missing]
                raise ValueError("Не заполнены обязательные компоненты: " + ", ".join(names))

            conn.execute("BEGIN")
            conn.execute(
                "UPDATE measurement_sessions SET measured_at = :at, notes = :notes "
                "WHERE id = :sid",
                {"at": measured_at, "notes": notes, "sid": session_id}
            )
            # Полная замена значений (проще, чем diff)
            conn.execute(
                "DELETE FROM measurement_values WHERE measurement_session_id = :sid",
                {"sid": session_id}
            )
            now = datetime_utils.get_now_iso()
            for comp_id, val in values.items():
                conn.execute(
                    "INSERT INTO measurement_values "
                    "(measurement_session_id, measurement_component_id, value, created_at) "
                    "VALUES (:sid, :cid, :val, :now)",
                    {"sid": session_id, "cid": comp_id, "val": float(val), "now": now}
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_session(self, session_id: int):
        """Удаляет сеанс. Значения удаляются каскадно (ON DELETE CASCADE)."""
        conn = self.db.connect()
        try:
            conn.execute(
                "DELETE FROM measurement_sessions WHERE id = :sid",
                {"sid": session_id}
            )
            conn.commit()
        finally:
            conn.close()

    def get_sessions_for_display(self, type_id: int | None = None,
                                 limit: int | None = None) -> list[dict]:
        """Список сеансов для «Истории».

        Args:
            type_id: фильтр по типу (None = все типы).
            limit: максимум сеансов (None = без ограничения).

        Returns:
            [{"id", "type_id", "type_name", "measured_at", "notes",
              "values": [{"component_id", "component_name", "value", "unit"}, ...]}, ...]
            Сортировка: по measured_at DESC.
        """
        conn = self.db.connect()
        try:
            where = ""
            params = {}
            if type_id is not None:
                where = "WHERE s.measurement_type_id = :tid"
                params["tid"] = type_id

            limit_clause = ""
            if limit is not None:
                limit_clause = f"LIMIT {int(limit)}"

            sessions_rows = conn.execute(
                f"SELECT s.id, s.measurement_type_id, t.name, s.measured_at, s.notes "
                f"FROM measurement_sessions s "
                f"JOIN measurement_types t ON s.measurement_type_id = t.id "
                f"{where} "
                f"ORDER BY s.measured_at DESC, s.id DESC "
                f"{limit_clause}",
                params
            ).fetchall()

            if not sessions_rows:
                return []

            session_ids = [r[0] for r in sessions_rows]
            placeholders = ",".join([f":sid{i}" for i in range(len(session_ids))])
            vals_params = {f"sid{i}": v for i, v in enumerate(session_ids)}

            values_rows = conn.execute(
                f"SELECT v.measurement_session_id, v.measurement_component_id, "
                f"c.name, v.value, u.display_name "
                f"FROM measurement_values v "
                f"JOIN measurement_components c ON v.measurement_component_id = c.id "
                f"JOIN units u ON c.unit_id = u.id "
                f"WHERE v.measurement_session_id IN ({placeholders}) "
                f"ORDER BY c.display_order, c.id",
                vals_params
            ).fetchall()

            values_by_session: dict[int, list[dict]] = {sid: [] for sid in session_ids}
            for v in values_rows:
                values_by_session[v[0]].append({
                    "component_id": v[1],
                    "component_name": v[2],
                    "value": v[3],
                    "unit": v[4],
                })

            result = []
            for s in sessions_rows:
                result.append({
                    "id": s[0],
                    "type_id": s[1],
                    "type_name": s[2],
                    "measured_at": s[3],
                    "notes": s[4],
                    "values": values_by_session.get(s[0], []),
                })
            return result
        finally:
            conn.close()

    def get_session_full(self, session_id: int) -> dict | None:
        """Полные данные сеанса для редактирования."""
        conn = self.db.connect()
        try:
            s = conn.execute(
                "SELECT s.id, s.measurement_type_id, s.measured_at, s.notes "
                "FROM measurement_sessions s WHERE s.id = :sid",
                {"sid": session_id}
            ).fetchone()
            if not s:
                return None

            vals = conn.execute(
                "SELECT measurement_component_id, value "
                "FROM measurement_values WHERE measurement_session_id = :sid",
                {"sid": session_id}
            ).fetchall()

            return {
                "id": s[0],
                "type_id": s[1],
                "measured_at": s[2],
                "notes": s[3],
                "values": {v[0]: v[1] for v in vals},
            }
        finally:
            conn.close()