-- migrations/007_add_regular_duties.sql
-- Регулярные обязанности (regular_duties) и отметки об их выполнении
-- (regular_duty_marks). Плюс поле activities.regular_duty_id.
--
-- Вариант A: activities.activity_type_id остаётся NOT NULL.
-- Триггер только ПРОВЕРЯЕТ совпадение типа активности с типом обязанности.
-- Подстановка activity_type_id при выборе обязанности — в UI
-- (manual_activities_tab.py) и в импорте (base_exchange_service.py).

-- =========================================================================
-- 1. Справочник регулярных обязанностей
-- =========================================================================

CREATE TABLE IF NOT EXISTS regular_duties (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL UNIQUE,         -- «Проверка уведомлений», «Обзор недели»
    description      TEXT,

    -- Тип активности, которым выполняется обязанность (обязательно).
    -- При выборе обязанности в UI activity_type_id подставляется из этого поля.
    activity_type_id INTEGER NOT NULL,

    -- За какой период обязанность должна быть выполнена.
    -- Определяет, в каком периоде ставится отметка.
    period_type      TEXT NOT NULL
                     CHECK (period_type IN ('day', 'week', 'month')),

    -- Контекст: роль / подроль (как в activity_types: оба nullable,
    -- role_id автозаполняется из sub_role_id триггером ниже).
    role_id          INTEGER,
    sub_role_id      INTEGER,

    created_at       TEXT,
    updated_at       TEXT,

    FOREIGN KEY (activity_type_id) REFERENCES activity_types(id) ON DELETE RESTRICT,
    FOREIGN KEY (role_id)          REFERENCES roles(id)          ON DELETE RESTRICT,
    FOREIGN KEY (sub_role_id)      REFERENCES sub_roles(id)      ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_regular_duties_activity_type
    ON regular_duties(activity_type_id);
CREATE INDEX IF NOT EXISTS idx_regular_duties_role
    ON regular_duties(role_id);
CREATE INDEX IF NOT EXISTS idx_regular_duties_sub_role
    ON regular_duties(sub_role_id);

-- =========================================================================
-- 2. Автозаполнение role_id из sub_role_id (как в activity_types)
-- =========================================================================

CREATE TRIGGER IF NOT EXISTS fill_role_on_duty_insert
AFTER INSERT ON regular_duties
FOR EACH ROW
WHEN NEW.sub_role_id IS NOT NULL AND NEW.role_id IS NULL
BEGIN
    UPDATE regular_duties
    SET role_id = (SELECT parent_role_id FROM sub_roles WHERE id = NEW.sub_role_id)
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS fill_role_on_duty_update
AFTER UPDATE OF sub_role_id ON regular_duties
FOR EACH ROW
WHEN NEW.sub_role_id IS NOT NULL
BEGIN
    UPDATE regular_duties
    SET role_id = (SELECT parent_role_id FROM sub_roles WHERE id = NEW.sub_role_id)
    WHERE id = NEW.id;
END;

-- При переезде подроли к другой роли — обновить role_id в обязанностях
-- (по образцу update_activities_on_sub_role_move из миграции 005).
CREATE TRIGGER IF NOT EXISTS update_duties_on_sub_role_move
AFTER UPDATE OF parent_role_id ON sub_roles
FOR EACH ROW
WHEN NEW.parent_role_id != OLD.parent_role_id
BEGIN
    UPDATE regular_duties
    SET role_id = NEW.parent_role_id
    WHERE sub_role_id = NEW.id;
END;

-- Автообновление updated_at (по образцу update_activity_timestamp).
CREATE TRIGGER IF NOT EXISTS update_duty_timestamp
AFTER UPDATE ON regular_duties
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE regular_duties
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;

-- =========================================================================
-- 3. Транзакционная таблица: отметки о выполнении обязанностей
-- =========================================================================
-- Одно поле status + mark_value с CHECK на согласованность:
--   status='done'     → mark_value = 100
--   status='not_done' → mark_value = 0
--   status='partial'  → mark_value в 1..99
-- Без UNIQUE(duty_id, period_id): за период можно отметить несколько раз
-- (переоткрыл → закрыл снова, или разные note). Индикаторы увидят
-- последнюю/агрегированную отметку — решится в calc_method.

CREATE TABLE IF NOT EXISTS regular_duty_marks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    duty_id     INTEGER NOT NULL,
    period_id   INTEGER NOT NULL,
    marked_at   TEXT NOT NULL,       -- ISO 8601: когда отметили (может быть задним числом)

    -- Статус выполнения и оценка (0..100). CHECK гарантирует согласованность.
    status      TEXT NOT NULL DEFAULT 'done'
                CHECK (status IN ('done', 'not_done', 'partial')),
    mark_value  INTEGER NOT NULL DEFAULT 100
                CHECK (mark_value >= 0 AND mark_value <= 100),

    note        TEXT,
    created_at  TEXT,
    updated_at  TEXT,

    FOREIGN KEY (duty_id)   REFERENCES regular_duties(id) ON DELETE RESTRICT,
    FOREIGN KEY (period_id) REFERENCES periods(id)        ON DELETE RESTRICT,

    CHECK (
        (status = 'done'     AND mark_value = 100) OR
        (status = 'not_done' AND mark_value = 0)   OR
        (status = 'partial'  AND mark_value BETWEEN 1 AND 99)
    )
);

CREATE INDEX IF NOT EXISTS idx_regular_duty_marks_duty_period
    ON regular_duty_marks(duty_id, period_id);

CREATE TRIGGER IF NOT EXISTS update_duty_mark_timestamp
AFTER UPDATE ON regular_duty_marks
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE regular_duty_marks
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;

-- =========================================================================
-- 4. Поле activities.regular_duty_id (nullable FK)
-- =========================================================================

ALTER TABLE activities ADD COLUMN regular_duty_id INTEGER NULL
    REFERENCES regular_duties(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_activities_duty
    ON activities(regular_duty_id);

-- =========================================================================
-- 5. Проверка совпадения типа активности с типом обязанности
-- =========================================================================
-- Вариант A: триггер только ПРОВЕРЯЕТ. Если regular_duty_id задан и
-- activity_type_id не совпадает с типом обязанности — ABORT.
-- Подстановка activity_type_id при выборе обязанности — в UI и импорте.

CREATE TRIGGER IF NOT EXISTS protect_activity_duty_consistency_insert
BEFORE INSERT ON activities
FOR EACH ROW
WHEN NEW.regular_duty_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT,
        'Тип активности не совпадает с типом регулярной обязанности.')
    WHERE NEW.activity_type_id != (
        SELECT activity_type_id FROM regular_duties
        WHERE id = NEW.regular_duty_id
    );
END;

CREATE TRIGGER IF NOT EXISTS protect_activity_duty_consistency_update
BEFORE UPDATE OF regular_duty_id, activity_type_id ON activities
FOR EACH ROW
WHEN NEW.regular_duty_id IS NOT NULL
BEGIN
    SELECT RAISE(ABORT,
        'Тип активности не совпадает с типом регулярной обязанности.')
    WHERE NEW.activity_type_id != (
        SELECT activity_type_id FROM regular_duties
        WHERE id = NEW.regular_duty_id
    );
END;