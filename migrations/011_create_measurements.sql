-- migrations/011_create_measurements.sql
-- Подсистема измерений (EAV-подход).
--
-- 5 таблиц:
--   units                  — справочник единиц измерения (seed в этой миграции)
--   measurement_types      — справочник типов («Вес», «Давление», «Накопления»)
--   measurement_components — компоненты типа («Систола», «Диастола», «Пульс»)
--   measurement_sessions   — сеансы измерения (когда, что)
--   measurement_values     — значения компонентов в сеансе (числа)
--
-- Подход к единицам: единица привязана к КОМПОНЕНТУ (не к значению).
-- Конверсии между единицами нет — пользователь пересчитывает сам.
-- Это осознанное решение (см. IMP в roadmap).
--
-- Секунды в measured_at обнуляются в коде (to_minute_iso), как в activities.

-- =========================================================================
-- 1. Справочник единиц измерения
-- =========================================================================
CREATE TABLE IF NOT EXISTS units (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL UNIQUE,          -- краткое: «кг», «см», «мм рт. ст.»
    full_name    TEXT NOT NULL,                 -- полное: «килограмм», «сантиметр»
    description  TEXT,                          -- «Единица массы», «Единица длины»
    created_at   TEXT,
    updated_at   TEXT,

    CHECK (length(trim(display_name)) > 0),
    CHECK (length(trim(full_name)) > 0)
);

-- =========================================================================
-- 2. Типы измерений
-- =========================================================================
CREATE TABLE IF NOT EXISTS measurement_types (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TEXT,
    updated_at  TEXT
);

-- =========================================================================
-- 3. Компоненты типов
-- =========================================================================
CREATE TABLE IF NOT EXISTS measurement_components (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    measurement_type_id INTEGER NOT NULL,
    name                TEXT NOT NULL,
    unit_id             INTEGER NOT NULL,
    display_order       INTEGER NOT NULL DEFAULT 1,
    is_required         INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT,
    updated_at          TEXT,

    FOREIGN KEY (measurement_type_id) REFERENCES measurement_types(id) ON DELETE RESTRICT,
    FOREIGN KEY (unit_id)             REFERENCES units(id)             ON DELETE RESTRICT,

    UNIQUE (measurement_type_id, name),
    CHECK (is_required IN (0, 1)),
    CHECK (display_order >= 0)
);

-- =========================================================================
-- 4. Сеансы измерений
-- =========================================================================
CREATE TABLE IF NOT EXISTS measurement_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    measurement_type_id INTEGER NOT NULL,
    measured_at         TEXT NOT NULL,
    notes               TEXT,
    created_at          TEXT,
    updated_at          TEXT,

    FOREIGN KEY (measurement_type_id) REFERENCES measurement_types(id) ON DELETE RESTRICT
);

-- =========================================================================
-- 5. Значения компонентов
-- =========================================================================
CREATE TABLE IF NOT EXISTS measurement_values (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    measurement_session_id   INTEGER NOT NULL,
    measurement_component_id INTEGER NOT NULL,
    value                    REAL NOT NULL,
    created_at               TEXT,
    updated_at               TEXT,

    FOREIGN KEY (measurement_session_id)   REFERENCES measurement_sessions(id)   ON DELETE CASCADE,
    FOREIGN KEY (measurement_component_id) REFERENCES measurement_components(id) ON DELETE RESTRICT,

    UNIQUE (measurement_session_id, measurement_component_id)
);

-- =========================================================================
-- 6. Индексы
-- =========================================================================
CREATE INDEX IF NOT EXISTS idx_measurement_components_type
    ON measurement_components(measurement_type_id);

CREATE INDEX IF NOT EXISTS idx_measurement_components_unit
    ON measurement_components(unit_id);

CREATE INDEX IF NOT EXISTS idx_measurement_sessions_type_time
    ON measurement_sessions(measurement_type_id, measured_at);

CREATE INDEX IF NOT EXISTS idx_measurement_sessions_time
    ON measurement_sessions(measured_at);

CREATE INDEX IF NOT EXISTS idx_measurement_values_session
    ON measurement_values(measurement_session_id);

CREATE INDEX IF NOT EXISTS idx_measurement_values_component
    ON measurement_values(measurement_component_id);

-- =========================================================================
-- 7. Seed: стартовый набор единиц (только русские)
-- =========================================================================
INSERT OR IGNORE INTO units (display_name, full_name, description, created_at)
VALUES
    ('кг',         'килограмм',              'Единица массы',                    strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')),
    ('см',         'сантиметр',              'Единица длины',                    strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')),
    ('мм рт. ст.', 'миллиметр ртутного столба', 'Единица давления',              strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')),
    ('уд/мин',     'ударов в минуту',        'Единица частоты сердечных сокращений', strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')),
    ('%',          'процент',                'Единица доли (например, % жира)',  strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')),
    ('ммоль/л',    'миллимоль на литр',      'Единица концентрации (например, глюкоза)', strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')),
    ('шт',         'штука',                  'Счётная единица',                  strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')),
    ('руб',        'рубль',                  'Денежная единица',                 strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours'));

-- =========================================================================
-- 8. Триггеры updated_at
-- =========================================================================
CREATE TRIGGER IF NOT EXISTS update_unit_timestamp
AFTER UPDATE ON units
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE units
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_measurement_type_timestamp
AFTER UPDATE ON measurement_types
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE measurement_types
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_measurement_component_timestamp
AFTER UPDATE ON measurement_components
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE measurement_components
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_measurement_session_timestamp
AFTER UPDATE ON measurement_sessions
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE measurement_sessions
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_measurement_value_timestamp
AFTER UPDATE ON measurement_values
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE measurement_values
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;