-- migrations/003_add_role_color.sql
-- Добавление колонки для хранения цвета фона роли.

ALTER TABLE roles ADD COLUMN color TEXT DEFAULT '#FFFFFF'; -- по умолчанию белый