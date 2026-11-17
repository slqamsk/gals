# GALS — Структура проекта

## Краткое описание файлов

### Ядро и утилиты

| Файл | Назначение |
| --- | --- |
| `app_config.py` | Класс `AppConfig` — пути к папкам, файлу БД, ассетам, миграциям |
| `constants.py` | Enum: `MetricType`, `GoalType`, `ValueType`, `CalcMethod`, `AffectAxis` |
| `database.py` | `Database` — подключение к SQLite, **атомарные** миграции по `PRAGMA user_version` (транзакция на миграцию, FK выключаются на время применения, автобэкапа нет) |
| `datetime_utils.py` | Инициализация таймзоны (UTC+3), `get_now_iso`, `to_display`, `to_datetime`, `to_minute_iso` |
| `defaults.py` | `DEFAULT_PREFERENCES` — все дефолтные настройки (сгруппированы по сущностям, с комментариями; мёртвых ключей не держим) |
| `score_calculator.py` | `ScoreCalculator` — перевод факта и цели в оценку 0–100 по `GoalType` |
| `ui_utils.py` | `format_period_label`, `MONTHS_RU`, `sort_sheet_data` — UI-текст и сортировка |

### Репозитории

| Файл | Сущность |
|---|---|
| `activities_repo.py` | `activities` (автозаполнение `created_at`, обнуление секунд, длительности nullable) |
| `activity_types_repo.py` | `activity_types` |
| `chart_repo.py` | Легаси `role_metrics`/`sub_role_metrics` + `metric_values` по периодам (с `metric_id`) |
| `indicator_repo.py` | `indicators` + `indicator_values` (с `affects`, `question_id`; score не хранится) |
| `measurements_repo.py` | `units`, `measurement_types`, `measurement_components`, `measurement_sessions`, `measurement_values` |
| `metrics_repo.py` | `metrics` + `metric_values` (сам пишет `created_at`/`updated_at` — триггеров нет) |
| `period_repo.py` | `periods` (создание, границы, `get_available_periods`) |
| `preferences_repo.py` | `preferences` (key-value JSON) |
| `questions_repo.py` | `questions`, `question_options`, `answers` |
| `regular_duties_repo.py` | `regular_duties` |
| `regular_duty_marks_repo.py` | `regular_duty_marks` |
| `roles_repo.py` | `roles` |
| `sub_roles_repo.py` | `sub_roles` |
| `web_time_events_repo.py` | `web_time_events` |

### Сервисы

| Файл | Назначение |
|---|---|
| `base_exchange_service.py` | Базовый класс импорта/экспорта, валидация FK, priority-словарь таблиц (уровни: `regular_duties`=4, `activities`/`indicators`/`regular_duty_marks`=5, `answers`/`indicator_values`/`metric_values`=6) |
| `excel_service.py` | Импорт/экспорт `.xlsx` (openpyxl) |
| `json_service.py` | Импорт/экспорт `.json` |
| `indicator_calculator.py` | Движок: `calc_duration`, `calc_start_time`, `calc_count`, `calc_duty_done`, `calc_duty_mark`, `calc_question_last` |
| `indicator_service.py` | Оркестратор: `recalculate_for_date` (day/week/month), валидация, `_calculate_period` (раздельно по осям; вес 0 остаётся нулём; метрика без индикаторов получает 0/0) |
| `web_sync.py` | `sync()`: fetch → INSERT OR IGNORE → DELETE на сервере |
| `web_events_service.py` | `add_sleep_from_web_events()`: предпроверка «все события типа в окне», дедупликация (sleep=последнее, wake=первое), создание активности, подробные ошибки |

### UI

| Файл | Что |
|---|---|
| `app_ui.py` | Главное окно, собирает верхние вкладки, `on_exit` сохраняет состояние |
| `main_tab.py` | «Главная» — заглушка со слоганом + кнопка «Выход» |
| `role_model_tab.py` | Контейнер «Ролевая модель» (Роли, Под-роли, Индикаторы, График метрик, График по периодам) |
| `role_tree_container.py` | Контейнер верхней «Дерево ролей» (Дерево ролей, Метрики, Связи ролей) |
| `roles_excel_tab.py` | Таблица «Роли» |
| `sub_roles_tab.py` | «Под-роли» — Master-Detail |
| `tree_tab.py` | «Дерево ролей» (с корнем «📁 Все роли», `roles_tree_state`) |
| `metrics_config_tab.py` | «Метрики» — Master-Detail (роль → метрики), `roles_tree_state` |
| `indicator_config_tab.py` | «Индикаторы» — тип / обязанность / вопрос + `affects` |
| `chart_tab.py` | «График метрик» (легаси) |
| `chart_metrics_tab.py` | «График по периодам» (на `metric_values`), диалог «Метрика: {name}» с двумя таблицами индикаторов по осям |
| `activities_tab.py` | Контейнер «Активности» (Ручная работа, Типы, Обязанности, Выполнение) |
| `manual_activities_tab.py` | «Ручная работа» (16 колонок; пикер даты-времени с независимыми датами; длительности — только введённое, пустое → NULL) |
| `activity_types_tab.py` | «Типы активностей» |
| `regular_duties_tab.py` | «Обязанности» (9 колонок) |
| `regular_duty_marks_tab.py` | «Выполнение обязанностей» (двойной клик по активности — диалог редактирования; NULL-длительность показывается пустой) |
| `role_links_tab.py` | «Связи ролей» (3 панели, 3 layout-режима, предзаполнение типа) |
| `measurements_tab.py` | Контейнер «Измерения» (Ввод измерения, История, Настройки) |
| `measurements_input_tab.py` | «Ввод измерения» — динамическая форма по компонентам типа |
| `measurements_history_tab.py` | «История» измерений (read-only таблица, ширины и сортировка сохраняются) |
| `measurements_settings_tab.py` | «Настройки» — типы/компоненты + единицы; сохраняются ширины трёх таблиц и разделитель |
| `questionnaires_tab.py` | Контейнер «Опросы» (Отмечание, История, Настройка) |
| `questionnaires_mark_tab.py` | «Отмечание» — дерево + форма с radio-кнопками; сохраняется разделитель |
| `questionnaires_history_tab.py` | «История» ответов (фильтры по периоду/вопросу; сохраняются ширины, разделитель, период, дата, вопрос) |
| `questionnaires_settings_tab.py` | «Настройка» — дерево ролей + вопросы (сверху) и варианты ответа (снизу); сохраняются ширины обеих таблиц и оба разделителя |
| `data_exchange_tab.py` | «Обмен данными» |
| `tools_tab.py` | Контейнер «Инструменты» |
| `tools_debt_tab.py` | «Техдолг» — читает `roadmap.md` |
| `tools_debug_tab.py` | «Служебные операции» — пересчёт индикаторов + корректировка периодов |
| `tools_web_events_tab.py` | «Web-события» — настройки, синхронизация, «Пометить все как обработанные», создание сна |

## Веб-часть (`../z`) — законсервирована

> **Статус:** серверная часть (`../z`) и клиентский код веб-синхронизации (`web_sync.py`, `web_events_service.py`, вкладка «Web-события») **законсервированы**. Пользователь пользуется тем, что разработано, но дальнейшее развитие отложено. Все технические долги по веб-API (TD-16) тоже отложены.

Деплоится на `slqa.ru` как `https://slqa.ru/z/`. Структура в проекте повторяет структуру на сервере:

| Файл | Назначение |
|---|---|
| `../z/index.html` | Страница с кнопками «Подъём» / «Отбой» для телефона |
| `../z/api/.htaccess` | Роутинг всех запросов в `index.php` + CORS |
| `../z/api/index.php` | Front controller: `POST /install`, `POST/GET /events/`, `DELETE /events/{id}` |
| `../z/api/db.php` | `get_pdo()`, `check_api_key()`, `ensure_schema()` |
| `../z/api/env_loader.php` | Парсер `.env` (без composer) |
| `../z/config/.htaccess` | `Require all denied` |
| `../z/config/.env.example` | Шаблон с `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASS`, `API_KEY` |
| `../z/config/.gitignore` | Игнорирует `.env` |
| `../z/config/README.md` | Инструкция по деплою |
| `../z/tests/gals.postman_collection.json` | Postman-коллекция: 10 запросов с проверками (авторизация, защита `.env`, CRUD событий, негативные кейсы) |

**Деплой:**
1. `../z/index.html` → `public_html/z/index.html`
2. `z/api/*` → `public_html/z/api/`
3. `z/config/*` → `public_html/z/config/`
4. `.env.example` → `.env`, заполнить реальными кредами

## Документация

Вся документация проекта лежит в папке `documents/` (не в корне).

| Файл | Содержание |
|---|---|
| `documents/architecture.md` | Философия, терминология, БД, семантика периодов, математика, UI/UX, паттерны |
| `documents/project_structure.md` | Этот файл — дерево файлов и краткое описание каждого |
| `documents/roadmap.md` | Технический долг (TD-01…TD-23), улучшения (IMP-01…IMP-08), планы развития, история закрытых пунктов |
| `private_documents/` | Личные заметки: привычки, ритуалы, работа с инсомнией (не документация проекта) |
| `documents/readme.md` | Промпт — инструкция для ассистента по внесению изменений |

## Структура проекта (не оформлять блоком, я документ читаю в исходном тексте)

gals/                                # корень проекта
├── gals.pyw                         # точка входа (двойной клик для запуска)
├── documents/                       # вся документация проекта
│   ├── architecture.md              # описание системы
│   ├── project_structure.md         # этот файл
│   ├── roadmap.md                   # техдолг и развитие
│   └── readme.md                    # только промпт (инструкция для ассистента)
├── requirements.txt                 # зависимости Python (openpyxl, python-dateutil, requests, tksheet, tkcalendar)
├── data/                            # создается автоматически
│   └── gals.db                      # файл базы данных SQLite (бэкап перед миграциями — вручную)
├── assets/
│   └── icon.ico                     # иконка приложения
├── migrations/                      # SQL-миграции (атомарно, по PRAGMA user_version)
│   ├── 001_init.sql                 # таблица preferences
│   ├── 002_create_roles.sql         # таблицы roles, sub_roles
│   ├── 003_add_role_color.sql       # добавление цвета роли
│   ├── 004_create_metrics.sql       # старые метрики (легаси)
│   ├── 005_create_activities.sql    # activity_types, activities, триггеры, дефолтный сон
│   ├── 006_create_metrics_system.sql # новая система (periods, metrics, indicators)
│   ├── 007_add_regular_duties.sql   # regular_duties, regular_duty_marks, activities.regular_duty_id
│   ├── 008_indicators_add_duty_id.sql # indicators: activity_type_id → NULL, + regular_duty_id, CHECK
│   ├── 009_web_time_events.sql      # web_time_events
│   ├── 010_add_duties_fields.sql    # regular_duties: execution_order, importance
│   ├── 011_create_measurements.sql  # units, measurement_types, measurement_components, measurement_sessions, measurement_values + seed единиц
│   ├── 012_create_questionnaires.sql # questions, question_options, answers
│   ├── 013_indicators_affects_and_questions.sql # indicators: + affects, + question_id, CHECK «ровно один из трёх»
│   └── 014_one_night_sleep_per_day.sql # уникальный индекс: один «Ночной сон» на календарную дату окончания
│
├── z/                               # веб-часть (деплоится на slqa.ru как /z/)
│   ├── index.html                   # страница с кнопками «Подъём» / «Отбой»
│   ├── api/                         # PHP-бэкенд (деплоится как /z/api/)
│   │   ├── .htaccess
│   │   ├── index.php
│   │   ├── db.php
│   │   └── env_loader.php
│   ├── config/                      # секреты (деплоится как /z/config/)
│   │   ├── .htaccess
│   │   ├── .env.example
│   │   ├── .gitignore
│   │   └── README.md
│   └── tests/
│       └── gals.postman_collection.json
│
└── src/                             # исходный код Python
    ├── __init__.py
    │
    ├── [ Ядро и утилиты ]
    ├── app_config.py
    ├── constants.py
    ├── database.py
    ├── datetime_utils.py
    ├── defaults.py
    ├── score_calculator.py
    ├── ui_utils.py
    │
    ├── [ Репозитории ]
    ├── activities_repo.py
    ├── activity_types_repo.py
    ├── chart_repo.py
    ├── indicator_repo.py
    ├── measurements_repo.py
    ├── metrics_repo.py
    ├── period_repo.py
    ├── preferences_repo.py
    ├── questions_repo.py
    ├── regular_duties_repo.py
    ├── regular_duty_marks_repo.py
    ├── roles_repo.py
    ├── sub_roles_repo.py
    └── web_time_events_repo.py
    │
    ├── [ Сервисы ]
    ├── base_exchange_service.py
    ├── excel_service.py
    ├── json_service.py
    ├── indicator_calculator.py
    ├── indicator_service.py
    ├── web_sync.py
    └── web_events_service.py
    │
    ├── [ Интерфейс (UI) ]
    ├── app_ui.py
    ├── main_tab.py
    │
    ├── role_model_tab.py
    ├── role_tree_container.py
    ├── roles_excel_tab.py
    ├── sub_roles_tab.py
    ├── tree_tab.py
    ├── metrics_config_tab.py
    ├── indicator_config_tab.py
    ├── chart_tab.py
    ├── chart_metrics_tab.py
    │
    ├── activities_tab.py
    ├── manual_activities_tab.py
    ├── activity_types_tab.py
    ├── regular_duties_tab.py
    ├── regular_duty_marks_tab.py
    ├── role_links_tab.py
    │
    ├── measurements_tab.py
    ├── measurements_input_tab.py
    ├── measurements_history_tab.py
    ├── measurements_settings_tab.py
    │
    ├── questionnaires_tab.py
    ├── questionnaires_mark_tab.py
    ├── questionnaires_history_tab.py
    ├── questionnaires_settings_tab.py
    │
    ├── data_exchange_tab.py
    │
    ├── tools_tab.py
    ├── tools_debt_tab.py
    ├── tools_debug_tab.py
    └── tools_web_events_tab.py
