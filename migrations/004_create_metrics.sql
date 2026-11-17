-- migrations/004_create_metrics.sql
-- Таблицы для хранения текущих метрик ролей и под-ролей.

-- Метрики для родительских ролей
CREATE TABLE IF NOT EXISTS role_metrics (
    role_id      INTEGER PRIMARY KEY,
    attention    REAL DEFAULT 0 CHECK (attention >= 0 AND attention <= 100),
    satisfaction REAL DEFAULT 0 CHECK (satisfaction >= 0 AND satisfaction <= 100),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
);

-- Метрики для под-ролей
CREATE TABLE IF NOT EXISTS sub_role_metrics (
    sub_role_id  INTEGER PRIMARY KEY,
    attention    REAL DEFAULT 0 CHECK (attention >= 0 AND attention <= 100),
    satisfaction REAL DEFAULT 0 CHECK (satisfaction >= 0 AND satisfaction <= 100),
    FOREIGN KEY (sub_role_id) REFERENCES sub_roles(id) ON DELETE CASCADE
);