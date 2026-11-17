-- migrations/001_init.sql
-- Начальная схема. Применяется первой на свежей базе.
-- Имя файла: <номер>_<описание>.sql — номер парсится кодом как версия.

CREATE TABLE IF NOT EXISTS preferences (
    key   TEXT PRIMARY KEY,   -- уникальное имя настройки (ключ)
    value TEXT NOT NULL       -- значение в формате JSON (восстанавливается при чтении)
);