import sqlite3
import os


BASE_DIR = os.path.dirname(__file__)
DB_PATH_ROOT = os.path.join(BASE_DIR, 'logistics.db')
DB_PATH_INSTANCE = os.path.join(BASE_DIR, 'instance', 'logistics.db')


if os.path.exists(DB_PATH_INSTANCE):
    DB_PATH = DB_PATH_INSTANCE
elif os.path.exists(DB_PATH_ROOT):
    DB_PATH = DB_PATH_ROOT
else:
    DB_PATH = None

def column_exists(cursor, table, column):
    """Проверяет существование колонки в таблице"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def update_schema():
    """Добавляет новые колонки в таблицу couriers"""
    
    if not DB_PATH:
        print(f"База данных не найдена")
        print("   Запустите Flask приложение для создания БД")
        return False
    
    print(f"Используется БД: {DB_PATH}")

    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        
        
        
        if not column_exists(cursor, 'couriers', 'auth_code'):
            cursor.execute('ALTER TABLE couriers ADD COLUMN auth_code VARCHAR(6)')
            print("Добавлена колонка 'auth_code' в таблицу 'couriers'")
        else:
            print("ℹ️  Колонка 'auth_code' уже существует")
        
        
        if not column_exists(cursor, 'couriers', 'telegram_chat_id'):
            cursor.execute('ALTER TABLE couriers ADD COLUMN telegram_chat_id VARCHAR(50)')
            print("✅ Добавлена колонка 'telegram_chat_id' в таблицу 'couriers'")
        else:
            print("ℹ️  Колонка 'telegram_chat_id' уже существует")
        
        conn.commit()
        print("\n🎉 Миграция завершена успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    update_schema()
