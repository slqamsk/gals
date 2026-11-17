# src/excel_service.py
# Сервис для импорта и экспорта таблиц в формат Excel (.xlsx).

import os
import json
from openpyxl import Workbook, load_workbook
from .base_exchange_service import BaseExchangeService


class ExcelService(BaseExchangeService):
    # Управляет экспортом и импортом данных в Excel.

    def export_tables(self, table_names: list[str], filepath: str):
        wb = Workbook()
        wb.remove(wb.active)  # удаляем пустой лист по умолчанию

        conn = self.db.connect()
        try:
            for table in table_names:
                ws = wb.create_sheet(title=table)
                headers, rows = self.get_table_data(table, conn)
                ws.append(headers)  # пишем заголовки

                for row in rows:
                    row_list = list(row)
                    # Если это таблица preferences, распаковываем JSON-значение
                    if table == "preferences":
                        try:
                            val_idx = headers.index("value")
                            row_list[val_idx] = json.loads(row_list[val_idx])
                        except (ValueError, json.JSONDecodeError, TypeError):
                            pass
                    ws.append(row_list)  # пишем строку данных
            wb.save(filepath)  # сохраняем файл на диск
        finally:
            conn.close()

    def import_tables(self, table_names: list[str], filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError("Файл не найден.")

        try:
            wb = load_workbook(filepath, data_only=True)
        except Exception as e:
            raise ValueError(f"Не удалось прочитать файл Excel. Ошибка: {e}")

        conn = self.db.connect()
        log_messages = []
        try:
            conn.execute("BEGIN")  # НАЧИНАЕМ ТРАНЗАКЦИЮ

            # СОРТИРУЕМ ТАБЛИЦЫ ПЕРЕД ИМПОРТОМ (родительские таблицы первыми)
            sorted_tables = self._sort_tables_for_import(table_names)

            for table in sorted_tables:
                if table not in wb.sheetnames:
                    raise ValueError(f"В файле отсутствует лист с именем '{table}'.")

                ws = wb[table]
                rows_data = list(ws.iter_rows(values_only=True))

                if not rows_data:
                    continue

                headers = [str(h).strip() for h in rows_data[0] if h is not None]
                data_rows = []

                for row in rows_data[1:]:
                    row_list = list(row)
                    # Если это таблица preferences, запаковываем значение обратно в JSON-строку для БД
                    if table == "preferences":
                        try:
                            val_idx = headers.index("value")
                            row_list[val_idx] = json.dumps(row_list[val_idx], ensure_ascii=False)
                        except ValueError:
                            pass
                    data_rows.append(row_list)

                count_insert, count_update = self.process_import(table, headers, data_rows, conn)
                log_messages.append(f"Таблица '{table}': добавлено {count_insert}, обновлено {count_update}.")

            conn.commit()  # ФИКСИРУЕМ ТРАНЗАКЦИЮ
            return log_messages
        except Exception as e:
            conn.rollback()  # ОТКАТЫВАЕМ ВСЁ при любой ошибке
            raise e
        finally:
            conn.close()