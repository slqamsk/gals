# src/json_service.py
# Сервис для импорта и экспорта таблиц в формат JSON (.json).

import os
import json
from .base_exchange_service import BaseExchangeService


class JsonService(BaseExchangeService):
    # Управляет экспортом и импортом данных в JSON.

    def export_tables(self, table_names: list[str], filepath: str):
        conn = self.db.connect()
        export_data = {}
        try:
            for table in table_names:
                headers, rows = self.get_table_data(table, conn)
                table_dicts = []

                for row in rows:
                    row_dict = dict(zip(headers, row))
                    # Если это таблица preferences, распаковываем JSON-значение
                    if table == "preferences" and "value" in row_dict:
                        try:
                            row_dict["value"] = json.loads(row_dict["value"])
                        except (json.JSONDecodeError, TypeError):
                            pass
                    table_dicts.append(row_dict)

                export_data[table] = table_dicts

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        finally:
            conn.close()

    def import_tables(self, table_names: list[str], filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError("Файл не найден.")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except Exception as e:
            raise ValueError(f"Не удалось прочитать файл JSON. Ошибка: {e}")

        conn = self.db.connect()
        log_messages = []
        try:
            conn.execute("BEGIN")  # НАЧИНАЕМ ТРАНЗАКЦИЮ

            # СОРТИРУЕМ ТАБЛИЦЫ ПЕРЕД ИМПОРТОМ (родительские таблицы первыми)
            sorted_tables = self._sort_tables_for_import(table_names)

            for table in sorted_tables:
                if table not in json_data:
                    raise ValueError(f"В файле отсутствует раздел (ключ) с именем '{table}'.")

                table_dicts = json_data[table]
                if not table_dicts:
                    continue

                headers = list(table_dicts[0].keys())
                data_rows = []

                for row_dict in table_dicts:
                    row_vals = []
                    for h in headers:
                        val = row_dict.get(h)
                        # Если это таблица preferences, запаковываем значение обратно в JSON-строку для БД
                        if table == "preferences" and h == "value":
                            val = json.dumps(val, ensure_ascii=False)
                        row_vals.append(val)
                    data_rows.append(row_vals)

                count_insert, count_update = self.process_import(table, headers, data_rows, conn)
                log_messages.append(f"Таблица '{table}': добавлено {count_insert}, обновлено {count_update}.")

            conn.commit()  # ФИКСИРУЕМ ТРАНЗАКЦИЮ
            return log_messages
        except Exception as e:
            conn.rollback()  # ОТКАТЫВАЕМ ВСЁ при любой ошибке
            raise e
        finally:
            conn.close()