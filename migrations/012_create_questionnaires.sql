-- migrations/012_create_questionnaires.sql
-- Подсистема субъективных оценок (опросники без сеансов).
--
-- 3 таблицы:
--   questions         — вопросы (с опциональной привязкой к роли/подроли)
--   question_options  — варианты ответов (значение 0-100 + описание)
--   answers           — ответы (снимок варианта + комментарий + время)
--
-- Каждый ответ — самостоятельный факт (без сеансов). `answers` хранит
-- СНИМОК value и option_description на момент ответа: если вариант потом
-- переименуют/изменят — старая история сохранит исходный смысл.
--
-- Привязка вопроса к роли/подроли — опциональна (оба поля могут быть NULL,
-- как в activity_types). Вопрос без привязки — «общий», доступен всем ролям.
--
-- Секунды в measured_at обнуляются в коде (to_minute_iso), как в activities.

-- =========================================================================
-- 1. Вопросы
-- =========================================================================
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    text        TEXT NOT NULL,

    role_id     INTEGER,
    sub_role_id INTEGER,

    created_at  TEXT,
    updated_at  TEXT,

    FOREIGN KEY (role_id)     REFERENCES roles(id)     ON DELETE RESTRICT,
    FOREIGN KEY (sub_role_id) REFERENCES sub_roles(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_questions_role
    ON questions(role_id);

CREATE INDEX IF NOT EXISTS idx_questions_sub_role
    ON questions(sub_role_id);

-- Автозаполнение role_id из sub_role_id (как в activity_types)
CREATE TRIGGER IF NOT EXISTS fill_role_on_question_insert
AFTER INSERT ON questions
FOR EACH ROW
WHEN NEW.sub_role_id IS NOT NULL AND NEW.role_id IS NULL
BEGIN
    UPDATE questions
    SET role_id = (SELECT parent_role_id FROM sub_roles WHERE id = NEW.sub_role_id)
    WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS fill_role_on_question_update
AFTER UPDATE OF sub_role_id ON questions
FOR EACH ROW
WHEN NEW.sub_role_id IS NOT NULL
BEGIN
    UPDATE questions
    SET role_id = (SELECT parent_role_id FROM sub_roles WHERE id = NEW.sub_role_id)
    WHERE id = NEW.id;
END;

-- При переезде подроли к другой роли — обновить role_id в вопросах
CREATE TRIGGER IF NOT EXISTS update_questions_on_sub_role_move
AFTER UPDATE OF parent_role_id ON sub_roles
FOR EACH ROW
WHEN NEW.parent_role_id != OLD.parent_role_id
BEGIN
    UPDATE questions
    SET role_id = NEW.parent_role_id
    WHERE sub_role_id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_question_timestamp
AFTER UPDATE ON questions
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE questions
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;

-- =========================================================================
-- 2. Варианты ответов
-- =========================================================================
CREATE TABLE IF NOT EXISTS question_options (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    value       INTEGER NOT NULL,
    description TEXT NOT NULL,

    created_at  TEXT,
    updated_at  TEXT,

    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE RESTRICT,

    UNIQUE (question_id, value),
    CHECK (value BETWEEN 0 AND 100),
    CHECK (length(trim(description)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_question_options_question
    ON question_options(question_id);

CREATE TRIGGER IF NOT EXISTS update_question_option_timestamp
AFTER UPDATE ON question_options
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE question_options
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;

-- =========================================================================
-- 3. Ответы
-- =========================================================================
-- Хранит снимок (value, option_description) на момент ответа.
-- question_id — единственная связь ответа с вопросом (FK на questions).
CREATE TABLE IF NOT EXISTS answers (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id        INTEGER NOT NULL,
    value              INTEGER NOT NULL,
    option_description TEXT NOT NULL,
    extra_comment      TEXT,
    measured_at        TEXT NOT NULL,

    created_at         TEXT,
    updated_at         TEXT,

    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE RESTRICT,

    CHECK (value BETWEEN 0 AND 100),
    CHECK (length(trim(option_description)) > 0)
);

CREATE INDEX IF NOT EXISTS idx_answers_question
    ON answers(question_id);

CREATE INDEX IF NOT EXISTS idx_answers_measured_at
    ON answers(measured_at);

CREATE TRIGGER IF NOT EXISTS update_answer_timestamp
AFTER UPDATE ON answers
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE answers
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;