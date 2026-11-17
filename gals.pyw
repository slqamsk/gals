# gals.pyw
# Заглушка GUI-программы (Windows). Точка входа в корне проекта.

from src.app_ui import main  # импорт из пакета src; корень проекта уже в sys.path

# защита от запуска при импорте
if __name__ == "__main__":
    main()  # запуск программы