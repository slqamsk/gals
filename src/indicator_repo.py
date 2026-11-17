# src/indicator_repo.py
# Репозиторий для работы с правилами (индикаторами) и их значениями.

from .database import Database


class IndicatorRepository:
    def __init__(self, db: Database):
        self.db = db

    def get_all(self) -> list[dict]:
        """Возвращает список всех индикаторов из базы данных (со всеми полями).

        Ровно одно из полей activity_type_id / regular_duty_id / question_id
        заполнено (CHECK в БД). Поле affects — обязательное ('satisfaction'|'attention').
        """
        conn = self.db.connect()
        try:
            cursor = conn.execute(
                "SELECT id, metric_id, activity_type_id, regular_duty_id, question_id, "
                "affects, "
                "name, description, unit, value_type, "
                "goal_type, target_value, goal_step, goal_penalty, weight, calc_method "
                "FROM indicators"
            )
            rows = cursor.fetchall()

            return [
                {
                    "id": r[0],
                    "metric_id": r[1],
                    "activity_type_id": r[2],
                    "regular_duty_id": r[3],
                    "question_id": r[4],
                    "affects": r[5],
                    "name": r[6],
                    "description": r[7],
                    "unit": r[8],
                    "value_type": r[9],
                    "goal_type": r[10],
                    "target_value": r[11],
                    "goal_step": r[12],
                    "goal_penalty": r[13],
                    "weight": r[14],
                    "calc_method": r[15],
                }
                for r in rows
            ]
        finally:
            conn.close()

    def add(self, metric_id: int, name: str, description: str,
            unit: str, value_type: str, goal_type: str, target_value: str,
            goal_step: float, goal_penalty: float, weight: int, calc_method: str,
            affects: str,
            activity_type_id: int | None = None,
            regular_duty_id: int | None = None,
            question_id: int | None = None):
        """Добавляет новый индикатор. Ровно одно из activity_type_id /
        regular_duty_id / question_id должно быть задано (CHECK в БД).
        affects — обязательный параметр ('satisfaction'|'attention')."""
        conn = self.db.connect()
        try:
            params = {
                "metric_id": metric_id,
                "activity_type_id": activity_type_id,
                "regular_duty_id": regular_duty_id,
                "question_id": question_id,
                "affects": affects,
                "name": name,
                "description": description,
                "unit": unit,
                "value_type": value_type,
                "goal_type": goal_type,
                "target_value": target_value,
                "goal_step": goal_step,
                "goal_penalty": goal_penalty,
                "weight": weight,
                "calc_method": calc_method,
            }
            conn.execute(
                "INSERT INTO indicators (metric_id, activity_type_id, regular_duty_id, question_id, "
                "affects, name, description, unit, "
                "value_type, goal_type, target_value, goal_step, goal_penalty, weight, calc_method) "
                "VALUES (:metric_id, :activity_type_id, :regular_duty_id, :question_id, "
                ":affects, :name, :description, :unit, "
                ":value_type, :goal_type, :target_value, :goal_step, :goal_penalty, :weight, :calc_method)",
                params
            )
            conn.commit()
        finally:
            conn.close()

    def update(self, indicator_id: int, metric_id: int, name: str,
               description: str, unit: str, value_type: str, goal_type: str,
               target_value: str, goal_step: float, goal_penalty: float, weight: int,
               calc_method: str, affects: str,
               activity_type_id: int | None = None,
               regular_duty_id: int | None = None,
               question_id: int | None = None):
        """Обновляет существующий индикатор. affects — обязательный."""
        conn = self.db.connect()
        try:
            params = {
                "id": indicator_id,
                "metric_id": metric_id,
                "activity_type_id": activity_type_id,
                "regular_duty_id": regular_duty_id,
                "question_id": question_id,
                "affects": affects,
                "name": name,
                "description": description,
                "unit": unit,
                "value_type": value_type,
                "goal_type": goal_type,
                "target_value": target_value,
                "goal_step": goal_step,
                "goal_penalty": goal_penalty,
                "weight": weight,
                "calc_method": calc_method,
            }
            conn.execute(
                "UPDATE indicators SET "
                "metric_id = :metric_id, "
                "activity_type_id = :activity_type_id, "
                "regular_duty_id = :regular_duty_id, "
                "question_id = :question_id, "
                "affects = :affects, "
                "name = :name, description = :description, unit = :unit, "
                "value_type = :value_type, goal_type = :goal_type, target_value = :target_value, "
                "goal_step = :goal_step, goal_penalty = :goal_penalty, "
                "weight = :weight, calc_method = :calc_method "
                "WHERE id = :id",
                params
            )
            conn.commit()
        finally:
            conn.close()

    def delete(self, indicator_id: int):
        """Удаляет индикатор по его ID."""
        conn = self.db.connect()
        try:
            conn.execute(
                "DELETE FROM indicators WHERE id = :id",
                {"id": indicator_id}
            )
            conn.commit()
        finally:
            conn.close()

    def get_values_for_period(self, period_id: int) -> dict[int, str]:
        """Все значения индикаторов за период: {indicator_id: actual_value}.

        Нужно для диалога «Метрика: {name}» на вкладке «График по периодам» —
        чтобы одним запросом подтянуть actual_value по всем индикаторам метрики.
        """
        conn = self.db.connect()
        try:
            rows = conn.execute(
                "SELECT indicator_id, actual_value FROM indicator_values "
                "WHERE period_id = :pid",
                {"pid": period_id}
            ).fetchall()
        finally:
            conn.close()
        return {row[0]: row[1] for row in rows}

    def save_value(self, indicator_id: int, period_id: int, actual_value: str, created_at: str):
        """Сохраняет или обновляет значение индикатора за период.

        Args:
            indicator_id (int): ID индикатора.
            period_id (int): ID периода.
            actual_value (str): Вычисленное значение.
            created_at (str): Время создания записи.
        """
        conn = self.db.connect()
        try:
            params = {
                "ind_id": indicator_id,
                "per_id": period_id,
                "act_val": actual_value,
                "created": created_at
            }

            conn.execute(
                "INSERT INTO indicator_values (indicator_id, period_id, actual_value, created_at) "
                "VALUES (:ind_id, :per_id, :act_val, :created) "
                "ON CONFLICT(indicator_id, period_id) DO UPDATE SET "
                "actual_value = excluded.actual_value, updated_at = :created",
                params
            )
            conn.commit()
        finally:
            conn.close()