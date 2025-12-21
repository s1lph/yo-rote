"""
yo.route - Миграция базы данных для производственной логистики

Добавляет новые колонки в таблицу orders:
- type: тип заказа (delivery/pickup)
- required_courier_id: жесткая привязка к курьеру
- time_window_start: начало временного окна (HH:MM)
- time_window_end: конец временного окна (HH:MM)
"""

import sqlite3
import os

# Определяем путь к базе данных (Flask использует instance folder)
BASE_DIR = os.path.dirname(__file__)
INSTANCE_DB = os.path.join(BASE_DIR, 'instance', 'logistics.db')
ROOT_DB = os.path.join(BASE_DIR, 'logistics.db')

# Проверяем оба возможных расположения
if os.path.exists(INSTANCE_DB) and os.path.getsize(INSTANCE_DB) > 0:
    DB_PATH = INSTANCE_DB
elif os.path.exists(ROOT_DB) and os.path.getsize(ROOT_DB) > 0:
    DB_PATH = ROOT_DB
else:
    DB_PATH = INSTANCE_DB  # Default для новых установок

# Альтернативный путь для PostgreSQL через переменную окружения
DATABASE_URL = os.getenv('DATABASE_URL')

def migrate_sqlite():
    """Миграция для SQLite"""
    print(f"📦 Подключение к SQLite: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print("❌ База данных не найдена. Запустите приложение для создания.")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Список новых колонок
    columns = [
        ("type", "VARCHAR(20) DEFAULT 'delivery'"),
        ("required_courier_id", "INTEGER REFERENCES couriers(id)"),
        ("time_window_start", "VARCHAR(5)"),
        ("time_window_end", "VARCHAR(5)")
    ]
    
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
            print(f"✅ Добавлена колонка: {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print(f"⏩ Колонка {col_name} уже существует")
            else:
                print(f"❌ Ошибка добавления {col_name}: {e}")
                raise
    
    conn.commit()
    conn.close()
    print("✅ Миграция SQLite завершена успешно!")
    return True


def migrate_postgres():
    """Миграция для PostgreSQL"""
    print(f"📦 Подключение к PostgreSQL...")
    
    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 не установлен. Установите: pip install psycopg2-binary")
        return False
    
    # Парсим DATABASE_URL
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Список новых колонок для PostgreSQL
    columns = [
        ("type", "VARCHAR(20) DEFAULT 'delivery'"),
        ("required_courier_id", "INTEGER REFERENCES couriers(id)"),
        ("time_window_start", "VARCHAR(5)"),
        ("time_window_end", "VARCHAR(5)")
    ]
    
    for col_name, col_type in columns:
        try:
            # PostgreSQL синтаксис с IF NOT EXISTS
            cursor.execute(f"""
                DO $$ 
                BEGIN
                    ALTER TABLE orders ADD COLUMN {col_name} {col_type};
                EXCEPTION
                    WHEN duplicate_column THEN 
                        RAISE NOTICE 'column {col_name} already exists';
                END $$;
            """)
            print(f"✅ Добавлена/проверена колонка: {col_name}")
        except Exception as e:
            print(f"❌ Ошибка добавления {col_name}: {e}")
            raise
    
    conn.commit()
    conn.close()
    print("✅ Миграция PostgreSQL завершена успешно!")
    return True


if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Миграция базы данных yo.route")
    print("   Производственная логистика v1.0")
    print("=" * 50)
    print()
    
    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        migrate_postgres()
    else:
        migrate_sqlite()
