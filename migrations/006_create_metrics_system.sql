-- 006_create_metrics_system.sql
-- Создание справочника периодов, реестра метрик, показателей и их фактических значений.
-- Включает: fact_start/fact_end для периодов, дефолтный тип "Ночной сон", защитные триггеры.

-- 1. Справочник периодов (день, неделя, месяц, спринт)
CREATE TABLE IF NOT EXISTS periods (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    period_type  TEXT NOT NULL,      -- 'day', 'week', 'month', 'sprint'
    period_value TEXT NOT NULL,      -- '2026-10-31', '2026-W44', 'Sprint-5'
    start_date   TEXT,               -- дата начала периода (YYYY-MM-DD)
    end_date     TEXT,               -- дата окончания периода (YYYY-MM-DD)

    -- Фактические границы периода (ISO 8601, UTC+3).
    -- Для дня: fact_start = начало самого раннего ночного сна,
    --          заканчивающегося в этот день (или 00:00, если сна нет);
    --          fact_end   = fact_start следующего дня (или 23:59:59).
    -- Полуинтервал [fact_start, fact_end) определяет принадлежность активности.
    fact_start   TEXT,
    fact_end     TEXT,

    UNIQUE(period_type, period_value)
);

-- 2. Реестр метрик (Кто именно оценивается и как часто)
CREATE TABLE IF NOT EXISTS metrics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_type  TEXT NOT NULL,

    role_id      INTEGER,            -- либо роль
    sub_role_id  INTEGER,            -- либо подроль

    created_at   TEXT,

    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT,
    FOREIGN KEY (sub_role_id) REFERENCES sub_roles(id) ON DELETE RESTRICT,

    -- Жесткое правило: либо роль, либо подроль (но не обе)
    CHECK ((role_id IS NOT NULL AND sub_role_id IS NULL) OR
           (role_id IS NULL AND sub_role_id IS NOT NULL))
);

-- Защита от дублей: одна метрика на роль/подроль для КАЖДОГО metric_type
CREATE UNIQUE INDEX IF NOT EXISTS idx_metrics_registry_role
ON metrics(role_id, metric_type) WHERE role_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_metrics_registry_sub_role
ON metrics(sub_role_id, metric_type) WHERE sub_role_id IS NOT NULL;

-- 3. Индикаторы (Правила, цели и методы расчета)
CREATE TABLE IF NOT EXISTS indicators (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_id        INTEGER NOT NULL,
    activity_type_id INTEGER NOT NULL,

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

    FOREIGN KEY (metric_id) REFERENCES metrics(id) ON DELETE RESTRICT,
    FOREIGN KEY (activity_type_id) REFERENCES activity_types(id) ON DELETE RESTRICT
);

-- 4. Значения индикаторов (История замеров за период)
CREATE TABLE IF NOT EXISTS indicator_values (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_id     INTEGER NOT NULL,
    period_id        INTEGER NOT NULL,
    actual_value     TEXT NOT NULL,

    created_at       TEXT,
    updated_at       TEXT,

    FOREIGN KEY (indicator_id) REFERENCES indicators(id) ON DELETE RESTRICT,
    FOREIGN KEY (period_id) REFERENCES periods(id) ON DELETE RESTRICT,

    UNIQUE(indicator_id, period_id)
);

-- 5. Итоговые метрики (для графика)
CREATE TABLE IF NOT EXISTS metric_values (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_id    INTEGER NOT NULL,
    period_id    INTEGER NOT NULL,

    attention    REAL DEFAULT 0 CHECK (attention >= 0 AND attention <= 100),
    satisfaction REAL DEFAULT 0 CHECK (satisfaction >= 0 AND satisfaction <= 100),

    created_at   TEXT,
    updated_at   TEXT,

    FOREIGN KEY (metric_id) REFERENCES metrics(id) ON DELETE RESTRICT,
    FOREIGN KEY (period_id) REFERENCES periods(id) ON DELETE RESTRICT,

    UNIQUE(metric_id, period_id)
);

