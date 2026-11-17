-- migrations/009_web_time_events.sql
-- Таблица для событий «Подъём»/«Отбой», синхронизированных с веб-API.
--
-- Синхронизация — тупой перенос: fetch с сервера → INSERT OR IGNORE сюда
-- → DELETE на сервере. Без дедупликации, без удаления локально.
--
-- UNIQUE(server_event_id) — идемпотентность: если DELETE на сервере упал
-- и событие придёт снова, дубль не создастся.
--
-- processed = 0 → ещё не использовано для создания сна;
-- processed = 1 → использовано (помечается кнопкой «Добавить сон»).

CREATE TABLE IF NOT EXISTS web_time_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    server_event_id   INTEGER NOT NULL UNIQUE,
    event_type        TEXT NOT NULL
                      CHECK (event_type IN ('wake','sleep')),
    event_time        TEXT NOT NULL,             -- ISO 8601, UTC+3
    processed         INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,             -- когда синхронизировали
    updated_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_web_time_events_time
    ON web_time_events(event_time);
CREATE INDEX IF NOT EXISTS idx_web_time_events_processed
    ON web_time_events(processed);

-- Автообновление updated_at (как в других таблицах)
CREATE TRIGGER IF NOT EXISTS update_web_time_event_timestamp
AFTER UPDATE ON web_time_events
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE web_time_events
    SET updated_at = strftime('%Y-%m-%dT%H:%M:%S+03:00', 'now', '+3 hours')
    WHERE id = NEW.id;
END;