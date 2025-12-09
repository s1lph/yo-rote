"""
yo.route - Migration Script for Bot Fields
Добавление новых полей для продвинутого Telegram-бота.

Безопасно добавляет колонки если их нет.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'logistics.db')


def column_exists(cursor, table, column):
    """Проверка существования колонки в таблице"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate():
    """Выполнение миграции"""
    print("🔄 Запуск миграции для полей Telegram-бота...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    migrations = [
        # Courier table - live tracking
        ('couriers', 'current_lat', 'FLOAT'),
        ('couriers', 'current_lon', 'FLOAT'),
        ('couriers', 'is_on_shift', 'BOOLEAN DEFAULT 0'),
        
        # Order table - proof of delivery
        ('orders', 'proof_image', 'VARCHAR(255)'),
        ('orders', 'failure_reason', 'VARCHAR(255)'),
    ]
    
    for table, column, column_type in migrations:
        if not column_exists(cursor, table, column):
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
                print(f"  ✅ Добавлена колонка {table}.{column}")
            except Exception as e:
                print(f"  ❌ Ошибка при добавлении {table}.{column}: {e}")
        else:
            print(f"  ⏭️  Колонка {table}.{column} уже существует")
    
    conn.commit()
    conn.close()
    
    print("✅ Миграция завершена!")


if __name__ == '__main__':
    migrate()
