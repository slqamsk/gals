# src/base_exchange_service.py
# Базовый класс для импорта/экспорта данных (общая логика).

import sqlite3
from .database import Database


class BaseExchangeService:
    # Содержит общую логику валидации и сохранения в БД.
    def __init__(self, db: Database):
        self.db = db

    # Вспомогательный метод: получает заголовки и все строки из таблицы БД.
    def get_table_data(self, table: str, conn) -> tuple[list[str], list[tuple]]:
        cursor = conn.execute(f"SELECT * FROM {table}")
        headers = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return headers, rows

    # Сортирует таблицы для импорта (родительские таблицы должны быть первыми).
    def _sort_tables_for_import(self, tables: list[str]) -> list[str]:
        # КОСТЫЛЬ: явный приоритет по уровням FK-зависимостей.
        # При добавлении новых таблиц сюда нужно вносить их.
        priority = {
            # уровень 1: ни на кого не ссылаются
            "preferences": 1,
            "roles": 1,
            "periods": 1,
            "units": 1,
            "measurement_types": 1,
            "web_time_events": 1,
            # уровень 2: ссылаются на уровень 1
            "sub_roles": 2,
            "role_metrics": 2,
            "measurement_components": 2,
            "measurement_sessions": 2,
            # уровень 3
            "questions": 3,
            "sub_role_metrics": 3,
            "activity_types": 3,
            "metrics": 3,
            "measurement_values": 3,
            # уровень 4: обязанности должны быть ДО activities/indicators
            "question_options": 4,
            "regular_duties": 4,
            # уровень 5: ссылаются на regular_duties
            "activities": 5,
            "indicators": 5,
            "regular_duty_marks": 5,
            # уровень 6: ссылаются на indicators
            "answers": 6,
            "indicator_values": 6,
            "metric_values": 6,
        }
        return sorted(tables, key=lambda t: priority.get(t, 99))

    # Проверяет внешние ключи для конкретной строки перед импортом.
    def _validate_foreign_keys(self, table: str, row_dict: dict, conn, row_idx: int):
        """Ищет нарушения FOREIGN KEY до попытки вставки/обновления."""
        # Получаем список внешних ключей для этой таблицы
        fks = conn.execute(f"PRAGMA foreign_key_list({table})").fetchall()

        for fk in fks:
            # Формат fk: (id, seq, parent_table, from_col, to_col, on_update, on_delete, match)
            parent_table = fk[2]
            from_col = fk[3]
            to_col = fk[4]

            val = row_dict.get(from_col)

            # Если значение не пустое, проверяем, существует ли оно в родительской таблице
            if val is not None and str(val).strip() != "":
                check_sql = f"SELECT 1 FROM {parent_table} WHERE {to_col} = ?"
                exists = conn.execute(check_sql, (val,)).fetchone()

                if not exists:
                    raise ValueError(
                        f"Ошибка целостности данных (строка {row_idx}):\n"
                        f"В таблице '{table}' указано значение '{val}' в колонке '{from_col}', "
                        f"но такой записи нет в таблице '{parent_table}' (колонка '{to_col}').\n"
                        f"Сначала импортируйте данные для таблицы '{parent_table}' или исправьте файл."
                    )

    # Основной метод импорта строк в БД.
    def process_import(self, table: str, headers: list[str], data_rows: list[list], conn) -> tuple[int, int]:
        db_info = conn.execute(f"PRAGMA table_info({table})").fetchall()
        db_columns = [row[1] for row in db_info]
        pk_cols = [row[1] for row in db_info if row[5] > 0]

        if set(headers) != set(db_columns):
            raise ValueError(
                f"Ошибка в таблице '{table}'. Ожидались колонки: {db_columns}. "
                f"В файле найдены: {headers}."
            )

        count_insert = 0
        count_update = 0

        for row_idx, row in enumerate(data_rows, start=2):
            if all(val is None or str(val).strip() == "" for val in row):
                continue

            row_dict = dict(zip(headers, row))

            # ПРОВЕРКА ВНЕШНИХ КЛЮЧЕЙ ПЕРЕД ЗАПИСЬЮ
            self._validate_foreign_keys(table, row_dict, conn, row_idx)

            has_pk = True
            for pk in pk_cols:
                pk_val = row_dict.get(pk)
                if pk_val is None or str(pk_val).strip() == "":
                    has_pk = False
                    break

            try:
                if has_pk:
                    set_cols = [c for c in headers if c not in pk_cols]
                    where_clause = " AND ".join([f"{c}=?" for c in pk_cols])

                    if set_cols:
                        set_clause = ", ".join([f"{c}=?" for c in set_cols])
                        sql_update = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
                        vals = [row_dict[c] for c in set_cols] + [row_dict[c] for c in pk_cols]
                        cursor = conn.execute(sql_update, vals)
                    else:
                        cursor = type('obj', (object,), {'rowcount': 1})

                    if cursor.rowcount == 0:
                        placeholders = ", ".join(["?"] * len(headers))
                        sql_insert = f"INSERT INTO {table} ({', '.join(headers)}) VALUES ({placeholders})"
                        conn.execute(sql_insert, [row_dict[c] for c in headers])
                        count_insert += 1
                    else:
                        count_update += 1
                else:
                    insert_cols = [c for c in headers if c not in pk_cols or row_dict.get(c) is not None]
                    placeholders = ", ".join(["?"] * len(insert_cols))
                    sql_insert = f"INSERT INTO {table} ({', '.join(insert_cols)}) VALUES ({placeholders})"
                    conn.execute(sql_insert, [row_dict[c] for c in insert_cols])
                    count_insert += 1
            except sqlite3.IntegrityError as e:
                # Ловим оставшиеся ошибки (например, UNIQUE constraint failed)
                raise sqlite3.IntegrityError(
                    f"Ошибка БД в таблице '{table}' (строка {row_idx}): {e}"
                )

        return count_insert, count_update