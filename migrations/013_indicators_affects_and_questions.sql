-- migrations/013_indicators_affects_and_questions.sql
-- Расширение indicators:
--   1. Новое поле affects ('satisfaction' | 'attention') — обязательное,
--      без DEFAULT. Каждый индикатор влияет на одну из двух осей.
--   2. Новый источник question_id (FK на questions).
--   3. CHECK "ровно один из трёх источников":
--      activity_type_id ИЛИ regular_duty_id ИЛИ question_id.
--
-- Существующим индикаторам проставляется affects='satisfaction',
-- question_id=NULL (все текущие индикаторы по факту считались как satisfaction).
--
-- SQLite не поддерживает ALTER COLUMN, поэтому пересоздаём таблицу.

PRAGMA foreign_keys = OFF;

CREATE TABLE indicators_new (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_id        INTEGER NOT NULL,

    -- Источник — ровно один из трёх.
    activity_type_id INTEGER,
    regular_duty_id  INTEGER,
    question_id      INTEGER,

    -- На что влияет индикатор (ось графика).
    -- 'satisfaction' — удовлетворённость результатом (ось X).
    -- 'attention'    — вложение усилий (ось Y).
    affects          TEXT NOT NULL
                     CHECK (affects IN ('satisfaction', 'attention')),

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
    FOREIGN KEY (question_id)      REFERENCES questions(id)      ON DELETE RESTRICT,

    -- Ровно один из трёх источников.
    CHECK (
        (CASE WHEN activity_type_id IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN regular_duty_id  IS NOT NULL THEN 1 ELSE 0 END +
         CASE WHEN question_id      IS NOT NULL THEN 1 ELSE 0 END) = 1
    )
);

INSERT INTO indicators_new (
    id, metric_id, activity_type_id, regular_duty_id, question_id,
    affects,
    name, description, unit, value_type,
    goal_type, target_value, goal_step, goal_penalty,
    weight, calc_method, created_at, updated_at
)
SELECT
    id, metric_id, activity_type_id, regular_duty_id, NULL,
    'satisfaction',
    name, description, unit, value_type,
    goal_type, target_value, goal_step, goal_penalty,
    weight, calc_method, created_at, updated_at
FROM indicators;

DROP TABLE indicators;
ALTER TABLE indicators_new RENAME TO indicators;

-- Индекс для FK question_id (SQLite не создаёт индексы на FK автоматически;
-- нужен для быстрой проверки RESTRICT при удалении question).
CREATE INDEX IF NOT EXISTS idx_indicators_question
    ON indicators(question_id);

PRAGMA foreign_keys = ON;