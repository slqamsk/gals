# src/chart_repo.py
# Репозиторий для работы с метриками (внимание и удовлетворенность).

from .database import Database


class ChartRepository:
    # Управляет чтением и записью метрик.
    def __init__(self, db: Database):
        self.db = db

    # ============================================================
    # ЛЕГАСИ-МЕТОДЫ (используются старой вкладкой "График метрик")
    # ============================================================

    # Возвращает объединенный список метрик для всех ролей и под-ролей (через UNION ALL).
    def get_all_metrics(self) -> list[dict]:
        conn = self.db.connect()
        try:
            query = """
                SELECT 
                    r.id AS entity_id, 
                    r.name, 
                    r.color, 
                    rm.attention, 
                    rm.satisfaction, 
                    'role' AS entity_type,
                    NULL AS parent_id
                FROM role_metrics rm
                JOIN roles r ON rm.role_id = r.id

                UNION ALL

                SELECT 
                    sr.id AS entity_id, 
                    sr.name, 
                    r.color, 
                    srm.attention, 
                    srm.satisfaction, 
                    'sub_role' AS entity_type,
                    sr.parent_role_id AS parent_id
                FROM sub_role_metrics srm
                JOIN sub_roles sr ON srm.sub_role_id = sr.id
                JOIN roles r ON sr.parent_role_id = r.id
            """
            rows = conn.execute(query).fetchall()

            # Превращаем кортежи в словари, жестко приводя числа к float
            result = []
            for row in rows:
                result.append({
                    "id": row[0],
                    "name": row[1],
                    "color": row[2] or "#FFFFFF",
                    "attention": float(row[3]) if row[3] is not None else 0.0,
                    "satisfaction": float(row[4]) if row[4] is not None else 0.0,
                    "type": row[5],
                    "parent_id": row[6]  # Добавили ID родительской роли
                })
            return result
        finally:
            conn.close()

    # Обновляет метрики конкретной сущности.
    def update_metric(self, entity_id: int, entity_type: str, attention: float, satisfaction: float):
        conn = self.db.connect()
        try:
            if entity_type == "role":
                conn.execute(
                    "UPDATE role_metrics SET attention = ?, satisfaction = ? WHERE role_id = ?",
                    (attention, satisfaction, entity_id)
                )
            else:
                conn.execute(
                    "UPDATE sub_role_metrics SET attention = ?, satisfaction = ? WHERE sub_role_id = ?",
                    (attention, satisfaction, entity_id)
                )
            conn.commit()
        finally:
            conn.close()

    # Сбрасывает все метрики (удаляет старые и создает новые с нулями).
    def reset_metrics(self):
        conn = self.db.connect()
        try:
            conn.execute("DELETE FROM role_metrics")
            conn.execute("DELETE FROM sub_role_metrics")

            roles = conn.execute("SELECT id FROM roles").fetchall()
            for role in roles:
                conn.execute(
                    "INSERT INTO role_metrics (role_id, attention, satisfaction) VALUES (?, 0, 0)",
                    (role[0],)
                )

            sub_roles = conn.execute("SELECT id FROM sub_roles").fetchall()
            for sr in sub_roles:
                conn.execute(
                    "INSERT INTO sub_role_metrics (sub_role_id, attention, satisfaction) VALUES (?, 0, 0)",
                    (sr[0],)
                )
            conn.commit()
        finally:
            conn.close()

    # ============================================================
    # НОВЫЕ МЕТОДЫ (для вкладки "График по периодам")
    # ============================================================

    # Возвращает периоды указанного типа, отсортированные по end_date DESC.
    def get_available_periods(self, period_type: str) -> list[tuple]:
        """Возвращает периоды указанного типа.

        Returns:
            list[(id, period_value, start_date, end_date), ...]
            Сортировка: сначала самые свежие (по end_date DESC).
        """
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT id, period_value, start_date, end_date FROM periods "
                "WHERE period_type = :ptype "
                "ORDER BY end_date DESC, id DESC",
                {"ptype": period_type}
            ).fetchall()
            return rows
        finally:
            conn.close()

    # Возвращает метрики с их значениями за конкретный период.
    def get_metrics_for_period(self, period_type: str, period_id: int) -> list[dict]:
        """Возвращает метрики с их значениями за конкретный период.

        Формат dict:
            {"id", "name", "color", "attention", "satisfaction",
             "type", "parent_id", "metric_id"}

        metric_id нужен диалогу «Метрика: {name}» для показа индикаторов метрики.
        Метрики, у которых нет metric_values за период, не возвращаются.
        """
        conn = self.db.connect()
        try:
            query = """
                SELECT
                    r.id AS entity_id,
                    r.name,
                    r.color,
                    mv.attention,
                    mv.satisfaction,
                    'role' AS entity_type,
                    NULL AS parent_id,
                    mv.metric_id
                FROM metric_values mv
                JOIN metrics m ON mv.metric_id = m.id
                JOIN roles r ON m.role_id = r.id
                WHERE m.metric_type = :mtype AND mv.period_id = :pid

                UNION ALL

                SELECT
                    sr.id AS entity_id,
                    sr.name,
                    r.color,
                    mv.attention,
                    mv.satisfaction,
                    'sub_role' AS entity_type,
                    sr.parent_role_id AS parent_id,
                    mv.metric_id
                FROM metric_values mv
                JOIN metrics m ON mv.metric_id = m.id
                JOIN sub_roles sr ON m.sub_role_id = sr.id
                JOIN roles r ON sr.parent_role_id = r.id
                WHERE m.metric_type = :mtype AND mv.period_id = :pid
            """
            rows = conn.execute(query, {"mtype": period_type, "pid": period_id}).fetchall()

            result = []
            for row in rows:
                result.append({
                    "id": row[0],
                    "name": row[1],
                    "color": row[2] or "#FFFFFF",
                    "attention": float(row[3]) if row[3] is not None else 0.0,
                    "satisfaction": float(row[4]) if row[4] is not None else 0.0,
                    "type": row[5],
                    "parent_id": row[6],
                    "metric_id": row[7],
                })
            return result
        finally:
            conn.close()