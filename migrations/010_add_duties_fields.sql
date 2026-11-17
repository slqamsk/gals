-- migrations/010_add_duties_fields.sql
-- Добавление полей порядка выполнения и важности для регулярных обязанностей.
-- Оба поля INTEGER NULL, без DEFAULT и без CHECK (по решению пользователя).

ALTER TABLE regular_duties ADD COLUMN execution_order INTEGER NULL;
ALTER TABLE regular_duties ADD COLUMN importance INTEGER NULL;