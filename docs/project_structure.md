# GALS — Структура проекта

gals/
├── assets/
│   └── icon.ico
├── data/
│   └── gals.db  # не загружается в git-репозиторий
├── docs/
│   ├── architecture.md
│   ├── project_passport.md
│   ├── project_structure.md
│   ├── prompts.md
│   ├── readme.md
│   └── roadmap.md
├── migrations/
│   ├── 001_init.sql
│   ├── 002_create_roles.sql
│   ├── 003_add_role_color.sql
│   ├── 004_create_metrics.sql
│   ├── 005_create_activities.sql
│   ├── 006_create_metrics_system.sql
│   ├── 007_add_regular_duties.sql
│   ├── 008_indicators_add_duty_id.sql
│   ├── 009_web_time_events.sql
│   ├── 010_add_duties_fields.sql
│   ├── 011_create_measurements.sql
│   ├── 012_create_questionnaires.sql
│   ├── 013_indicators_affects_and_questions.sql
│   └── 014_one_night_sleep_per_day.sql
├── src/
│   ├── __init__.py
│   ├── activities_repo.py
│   ├── activities_tab.py
│   ├── activity_types_repo.py
│   ├── activity_types_tab.py
│   ├── app_config.py
│   ├── app_ui.py
│   ├── base_exchange_service.py
│   ├── chart_metrics_tab.py
│   ├── chart_repo.py
│   ├── chart_tab.py
│   ├── constants.py
│   ├── data_exchange_tab.py
│   ├── database.py
│   ├── datetime_utils.py
│   ├── defaults.py
│   ├── excel_service.py
│   ├── indicator_calculator.py
│   ├── indicator_config_tab.py
│   ├── indicator_repo.py
│   ├── indicator_service.py
│   ├── json_service.py
│   ├── main_tab.py
│   ├── manual_activities_tab.py
│   ├── measurements_history_tab.py
│   ├── measurements_input_tab.py
│   ├── measurements_repo.py
│   ├── measurements_settings_tab.py
│   ├── measurements_tab.py
│   ├── metrics_config_tab.py
│   ├── metrics_repo.py
│   ├── period_repo.py
│   ├── preferences_repo.py
│   ├── questionnaires_history_tab.py
│   ├── questionnaires_mark_tab.py
│   ├── questions_repo.py
│   ├── questionnaires_settings_tab.py
│   ├── questionnaires_tab.py
│   ├── regular_duties_repo.py
│   ├── regular_duties_tab.py
│   ├── regular_duty_marks_repo.py
│   ├── regular_duty_marks_tab.py
│   ├── role_links_tab.py
│   ├── role_model_tab.py
│   ├── role_tree_container.py
│   ├── roles_excel_tab.py
│   ├── roles_repo.py
│   ├── score_calculator.py
│   ├── sub_roles_repo.py
│   ├── sub_roles_tab.py
│   ├── tools_debt_tab.py
│   ├── tools_debug_tab.py
│   ├── tools_tab.py
│   ├── tools_web_events_tab.py
│   ├── tree_tab.py
│   ├── ui_utils.py
│   ├── web_events_service.py
│   ├── web_sync.py
│   └── web_time_events_repo.py
├── z/
│   ├── api/
│   │   ├── .htaccess
│   │   ├── db.php
│   │   ├── env_loader.php
│   │   └── index.php
│   ├── config/
│   │   ├── .env.example
│   │   ├── .gitignore
│   │   ├── .htaccess
│   │   └── README.md
│   ├── tests/
│   │   └── gals.postman_collection.json
│   └── index.html
├── .gitattributes
├── .gitignore
├── gals.pyw
└── requirements.txt