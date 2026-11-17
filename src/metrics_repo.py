# src/metrics_repo.py
# Репозиторий для работы с реестром метрик.

from . import datetime_utils
from .database import Database
from .constants import MetricType


class MetricsRepository:
    def __init__(self, db: Database):
        self.db = db

    def get_all_metrics(self) -> list[dict]:
        """Возвращает список всех созданных метрик с привязкой к сущностям."""
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id, metric_type, role_id, sub_role_id FROM metrics"
            ).fetchall()
            return [
                {"id": r[0], "type": r[1], "role_id": r[2], "sub_role_id": r[3]}
                for r in rows
            ]
        finally:
            conn.close()

    def get_metrics_for_entity(self, entity_type: str, entity_id: int) -> set[str]:
        """Возвращает множество типов метрик, которые есть у конкретной роли/подроли."""
        conn = self.db.connect()
        try:
            if entity_type == "role":
                rows = conn.execute(
                    "SELECT metric_type FROM metrics WHERE role_id = :eid",
                    {"eid": entity_id}
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT metric_type FROM metrics WHERE sub_role_id = :eid",
                    {"eid": entity_id}
                ).fetchall()
            return {r[0] for r in rows}
        finally:
            conn.close()

    def add_metric(self, entity_type: str, entity_id: int, metric_type: MetricType):
        """Создает новую метрику для сущности."""
        conn = self.db.connect()
        try:
            if entity_type == "role":
                conn.execute(
                    "INSERT INTO metrics (metric_type, role_id) VALUES (:mtype, :eid)",
                    {"mtype": metric_type.value, "eid": entity_id}
                )
            else:
                conn.execute(
                    "INSERT INTO metrics (metric_type, sub_role_id) VALUES (:mtype, :eid)",
                    {"mtype": metric_type.value, "eid": entity_id}
                )
            conn.commit()
        finally:
            conn.close()

    def delete_metric(self, entity_type: str, entity_id: int, metric_type: MetricType):
        """Удаляет метрику у сущности."""
        conn = self.db.connect()
        try:
            if entity_type == "role":
                conn.execute(
                    "DELETE FROM metrics WHERE role_id = :eid AND metric_type = :mtype",
                    {"eid": entity_id, "mtype": metric_type.value}
                )
            else:
                conn.execute(
                    "DELETE FROM metrics WHERE sub_role_id = :eid AND metric_type = :mtype",
                    {"eid": entity_id, "mtype": metric_type.value}
                )
            conn.commit()
        finally:
            conn.close()

    def save_metric_value(self, metric_id: int, period_id: int, attention: float, satisfaction: float):
        """Сохраняет итоговые значения метрики за период.

        created_at/updated_at заполняются здесь: триггеров на metric_values нет.
        При обновлении created_at не меняется.
        """
        conn = self.db.connect()
        try:
            params = {
                "metric_id": metric_id,
                "period_id": period_id,
                "attention": attention,
                "satisfaction": satisfaction,
                "now": datetime_utils.get_now_iso(),
            }
            conn.execute(
                "INSERT INTO metric_values (metric_id, period_id, attention, satisfaction, "
                "created_at, updated_at) "
                "VALUES (:metric_id, :period_id, :attention, :satisfaction, :now, :now) "
                "ON CONFLICT(metric_id, period_id) DO UPDATE SET "
                "attention = excluded.attention, satisfaction = excluded.satisfaction, "
                "updated_at = :now",
                params
            )
            conn.commit()
        finally:
            conn.close()