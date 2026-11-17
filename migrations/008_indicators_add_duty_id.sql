-- migrations/008_indicators_add_duty_id.sql
-- Индикатор может опираться либо на activity_type, либо на regular_duty.
-- SQLite не поддерживает ALTER COLUMN ... DROP NOT NULL, поэтому пересоздаём.
--
-- Порядок:
--   1. Выключить foreign_keys (иначе DROP TABLE indicators упадёт из-за FK
--      от indicator_values).
--   2. Создать indicators_new с новой схемой (activity_type_id NULL,
--      regular_duty_id NULL, CHECK «ровно одно из двух»).
--   3. Перенести данные (id сохраняется — indicator_values не пострадают).
--   4. DROP TABLE indicators.
--   5. RENAME indicators_new → indicators.
--   6. Включить foreign_keys обратно.

PRAGMA foreign_keys = OFF;

CREATE TABLE indicators_new (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_id        INTEGER NOT NULL,

    -- Ровно одно из двух: либо тип активности, либо регулярная обязанность.
    activity_type_id INTEGER,
    regular_duty_id  INTEGER,

    name             TEXT NOT NULL,
    description      TEXT,
    unit             TEXT,
    value_type       TEXT NOT NULL DEFAULT 'number',

    goal_type        TEXT NOT NULL DEFAULT 'maximize',
    target_value     TEXT NOT NULL,
    goal_step        REAL DEFAULT 0,
    goal_penalty     REAL DEFAULT 0,

    weight           INTEGER DEFAULT 50,
    calc_method      TEXT NOT NULL,

    created_at       TEXT,
    updated_at       TEXT,

    FOREIGN KEY (metric_id)        REFERENCES metrics(id)        ON DELETE RESTRICT,
    FOREIGN KEY (activity_type_id) REFERENCES activity_types(id) ON DELETE RESTRICT,
    FOREIGN KEY (regular_duty_id)  REFERENCES regular_duties(id) ON DELETE RESTRICT,

    CHECK (
        (activity_type_id IS NOT NULL AND regular_duty_id IS NULL) OR
        (activity_type_id IS NULL     AND regular_duty_id IS NOT NULL)
    )
);

INSERT INTO indicators_new (
    id, metric_id, activity_type_id, regular_duty_id,
    name, description, unit, value_type,
    goal_type, target_value, goal_step, goal_penalty,
    weight, calc_method, created_at, updated_at
)
SELECT
    id, metric_id, activity_type_id, NULL,
    name, description, unit, value_type,
    goal_type, target_value, goal_step, goal_penalty,
    weight, calc_method, created_at, updated_at
FROM indicators;

DROP TABLE indicators;
ALTER TABLE indicators_new RENAME TO indicators;

PRAGMA foreign_keys = ON;