-- migrations/002_create_roles.sql
-- Создание таблиц ролей и под-ролей.

-- 1. Сначала создаём родительскую таблицу ролей
CREATE TABLE IF NOT EXISTS roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT, -- уникальный ID (автоинкремент)
    name        TEXT NOT NULL UNIQUE,              -- название роли (уникальное)
    description TEXT                               -- описание роли (может быть пустым)
);

-- 2. Затем создаём дочернюю таблицу под-ролей
CREATE TABLE IF NOT EXISTS sub_roles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT, -- уникальный ID
    name           TEXT NOT NULL,                     -- название под-роли
    description    TEXT,                              -- описание
    parent_role_id INTEGER NOT NULL,                  -- ссылка на родительскую роль
    FOREIGN KEY (parent_role_id) REFERENCES roles(id) ON DELETE RESTRICT -- запрет удаления, если есть под-роли
);