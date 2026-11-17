# src/preferences_repo.py
# Класс-репозиторий для работы с предпочтениями пользователя в БД.

import json
from .database import Database
from .defaults import DEFAULT_PREFERENCES


class PreferencesRepository:
    # Управляет чтением и записью предпочтений в таблицу preferences.
    def __init__(self, db: Database):
        self.db = db  # сохраняем ссылку на базу данных

    # Засеивает таблицу дефолтными предпочтениями при первом запуске.
    def init_defaults(self):
        conn = self.db.connect()  # открываем соединение

        # выполняем действия с автоматическим закрытием соединения
        try:
            # проходим по всем дефолтным предпочтениям
            for key, value in DEFAULT_PREFERENCES.items():
                # вставляем предпочтение в таблицу preferences, если его ещё нет
                conn.execute(
                    "INSERT OR IGNORE INTO preferences(key, value) VALUES(?, ?)",
                    (key, json.dumps(value, ensure_ascii=False)),
                )
            conn.commit()  # фиксируем изменения
        finally:
            conn.close()  # закрываем соединение

    # Возвращает значение с восстановленным типом (int/str/bool/…).
    def get(self, key: str):
        conn = self.db.connect()  # открываем соединение

        # выполняем запрос с автоматическим закрытием соединения
        try:
            # выполняем параметризованный запрос к таблице preferences
            row = conn.execute(
                "SELECT value FROM preferences WHERE key = ?", (key,)
            ).fetchone()
        finally:
            conn.close()  # закрываем соединение

        # если предпочтения нет в БД
        if row is None:
            return DEFAULT_PREFERENCES.get(key)  # возвращаем дефолтное значение
        return json.loads(row[0])  # декодируем JSON-строку обратно в Python-объект

    # Вставляет или обновляет значение.
    def set(self, key: str, value):
        conn = self.db.connect()  # открываем соединение

        # выполняем UPSERT с автоматическим закрытием соединения
        try:
            # выполняем UPSERT в таблицу preferences
            conn.execute(
                "INSERT INTO preferences(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            conn.commit()  # фиксируем изменения
        finally:
            conn.close()  # закрываем соединение

    # Возвращает снимок всех предпочтений: дефолты + данные из БД.
    def get_all(self) -> dict:
        conn = self.db.connect()  # открываем соединение

        # получаем данные с автоматическим закрытием соединения
        try:
            # получаем все ключи и значения из таблицы preferences
            rows = conn.execute("SELECT key, value FROM preferences").fetchall()
        finally:
            conn.close()  # закрываем соединение

        result = dict(DEFAULT_PREFERENCES)  # создаём копию дефолтных предпочтений

        # проходим по данным из БД
        for key, raw in rows:
            result[key] = json.loads(raw)  # перезаписываем значениями из БД

        return result  # возвращаем итоговый словарь