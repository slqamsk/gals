-- migrations/005_create_activities.sql
-- Создание справочника типов активностей и таблицы фактов (активностей).
-- Включает: дефолтный тип "Ночной сон", защитные триггеры и индексы.

-- 1. Справочник типов активностей (Шаблон)
CREATE TABLE IF NOT EXISTS activity_types (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    default_role_id INTEGER,
    default_sub_role_id INTEGER,
    usage_frequency INTEGER DEFAULT 1,
    importance INTEGER DEFAULT 1,

    FOREIGN KEY (default_role_id) REFERENCES roles(id) ON DELETE RESTRICT,
    FOREIGN KEY (default_sub_role_id) REFERENCES sub_roles(id) ON DELETE RESTRICT
);

-- 2. Основная таблица активностей (Сырые факты)
CREATE TABLE IF NOT EXISTS activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_type_id INTEGER NOT NULL,
    role_id INTEGER,
    sub_role_id INTEGER,

    start_time TEXT,
    end_time TEXT,
    duration INTEGER,
    clean_duration INTEGER,
    breaks_duration INTEGER DEFAULT 0,
    engagement_percentage INTEGER DEFAULT 100,

    source TEXT,
    is_estimated BOOLEAN DEFAULT 0,
    notes TEXT,

    created_at TEXT,
    updated_at TEXT,

    FOREIGN KEY (activity_type_id) REFERENCES activity_types(id) ON DELETE RESTRICT,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT,
    FOREIGN KEY (sub_role_id) REFERENCES sub_roles(id) ON DELETE RESTRICT
);

-- 3. Индексы для быстрого поиска по датам и типам
CREATE INDEX IF NOT EXISTS idx_activities_type ON activities(activity_type_id);
CREATE INDEX IF NOT EXISTS idx_activities_start ON activities(start_time);

-- 4. Дефолтный тип активности "Ночной сон" (id=1, обязательный)
INSERT OR IGNORE INTO activity_types
    (id, name, description, usage_frequency, importance)
VALUES
    (1, 'Ночной сон', 'Ночной сон — обязательная активность. Не удаляйте и не переименовывайте её.', 10, 10);

-- =========================================================================
-- 5. ТРИГГЕРЫ ДЛЯ ТАБЛИЦЫ activity_types
-- =========================================================================

-- 5.1. Защита "Ночного сна" от удаления
CREATE TRIGGER IF NOT EXISTS protect_night_sleep_delete
BEFORE DELETE ON activity_types
FOR EACH ROW
WHEN OLD.id = 1
BEGIN
    SELECT RAISE(ABORT, 'Тип активности id=1 "Ночной сон" нельзя удалить.');
END;

-- 5.2. Защита "Ночного сна" от переименования
CREATE TRIGGER IF NOT EXISTS protect_night_sleep_rename
BEFORE UPDATE OF name ON activity_types
FOR EACH ROW
WHEN OLD.id = 1 AND NEW.name != OLD.name
BEGIN
    SELECT RAISE(ABORT, 'Имя типа активности id=1 "Ночной сон" нельзя изменить.');
END;

-- 5.3. Автозаполнение default_role_id при вставке (из миграции 006)
CREATE TRIGGER IF NOT EXISTS fill_default_role_on_type_insert
AFTER INSERT ON activity_types
FOR EACH ROW
WHEN NEW.default_sub_role_id IS NOT NULL AND NEW.default_role_id IS NULL
BEGIN
    UPDATE activity_types
    SET default_role_id = (SELECT parent_role_id FROM sub_roles WHERE id = NEW.default_sub_role_id)
    WHERE id = NEW.id;
END;

-- 5.4. Автозаполнение default_role_id при обновлении (из миграции 006)
CREATE TRIGGER IF NOT EXISTS fill_default_role_on_type_update
AFTER UPDATE OF default_sub_role_id ON activity_types
FOR EACH ROW
WHEN NEW.default_sub_role_id IS NOT NULL
BEGIN
    UPDATE activity_types
    SET default_role_id = (SELECT parent_role_id FROM sub_roles WHERE id = NEW.default_sub_role_id)
    WHERE id = NEW.id;
END;

-- =========================================================================
-- 6. ТРИГГЕРЫ ДЛЯ ТАБЛИЦЫ activities
-- =========================================================================

-- 6.1. Автозаполнение role_id, если при вставке указан sub_role_id
CREATE TRIGGER IF NOT EXISTS fill_role_on_activity_insert
AFTER INSERT ON activities
FOR EACH ROW
WHEN NEW.sub_role_id IS NOT NULL AND NEW.role_id IS NULL
BEGIN
    UPDATE activities
    SET role_id = (SELECT parent_role_id FROM sub_roles WHERE id = NEW.sub_role_id)
    WHERE id = NEW.id;
END;

-- 6.2. Пересчет role_id, если в активности поменяли подроль
CREATE TRIGGER IF NOT EXISTS fill_role_on_activity_update
AFTER UPDATE OF sub_role_id ON activities
FOR EACH ROW
WHEN NEW.sub_role_id IS NOT NULL
BEGIN
    UPDATE activities
    SET role_id = (SELECT parent_role_id FROM sub_roles WHERE id = NEW.sub_role_id)
    WHERE id = NEW.id;
END;

-- 6.3. Обновление исторических активностей при "переезде" подроли к другой роли
CREATE TRIGGER IF NOT EXISTS update_activities_on_sub_role_move
AFTER UPDATE OF parent_role_id ON sub_roles
FOR EACH ROW
WHEN NEW.parent_role_id != OLD.parent_role_id
BEGIN
    UPDATE activities
    SET role_id = NEW.parent_role_id
    WHERE sub_role_id = NEW.id;
END;

-- 6.4. Автообновление поля updated_at при изменении активности
CREATE TRIGGER IF NOT EXISTS update_activity_timestamp
AFTER UPDATE ON activities
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE activities
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;