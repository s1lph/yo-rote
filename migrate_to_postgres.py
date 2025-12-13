"""
Скрипт миграции данных из SQLite в PostgreSQL

Использование:
1. Установи переменные окружения:
   - SQLITE_DATABASE_URL: путь к SQLite базе (sqlite:///logistics.db)
   - DATABASE_URL: URL PostgreSQL базы на Railway

2. Запусти скрипт:
   python migrate_to_postgres.py
"""

import os
import sys
from datetime import datetime

# Настройка путей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def create_app(database_url):
    """Создает Flask приложение с указанной базой данных"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    return app


def migrate_data():
    """Миграция данных из SQLite в PostgreSQL"""
    
    # URL баз данных
    sqlite_url = os.getenv('SQLITE_DATABASE_URL', 'sqlite:///logistics.db')
    postgres_url = os.getenv('DATABASE_URL')
    
    if not postgres_url:
        print("❌ Ошибка: DATABASE_URL (PostgreSQL) не установлен")
        print("   Установите переменную окружения DATABASE_URL")
        return False
    
    # Railway использует postgres://, но SQLAlchemy требует postgresql://
    if postgres_url.startswith('postgres://'):
        postgres_url = postgres_url.replace('postgres://', 'postgresql://', 1)
    
    print(f"📂 SQLite источник: {sqlite_url}")
    print(f"🐘 PostgreSQL назначение: {postgres_url[:50]}...")
    
    # Создаем движки баз данных
    sqlite_engine = create_engine(sqlite_url)
    postgres_engine = create_engine(postgres_url)
    
    # Создаем сессии
    SQLiteSession = sessionmaker(bind=sqlite_engine)
    PostgresSession = sessionmaker(bind=postgres_engine)
    
    sqlite_session = SQLiteSession()
    postgres_session = PostgresSession()
    
    try:
        # Импортируем модели для создания таблиц
        from models import db, User, Courier, Order, Route, Point
        
        # Создаем таблицы в PostgreSQL
        print("\n📋 Создание таблиц в PostgreSQL...")
        
        # Создаем Flask приложение для работы с моделями
        app = create_app(postgres_url)
        db.init_app(app)
        
        with app.app_context():
            db.create_all()
            print("✅ Таблицы созданы")
        
        # Порядок миграции (учитываем внешние ключи)
        tables = [
            ('users', User),
            ('points', Point),
            ('couriers', Courier),
            ('routes', Route),
            ('orders', Order),
        ]
        
        for table_name, Model in tables:
            print(f"\n🔄 Миграция таблицы: {table_name}")
            
            # Читаем данные из SQLite
            try:
                result = sqlite_session.execute(text(f"SELECT * FROM {table_name}"))
                rows = result.fetchall()
                columns = result.keys()
                
                if not rows:
                    print(f"   ⚪ Таблица пуста, пропускаем")
                    continue
                
                print(f"   📊 Найдено записей: {len(rows)}")
                
                # Вставляем в PostgreSQL
                with app.app_context():
                    for row in rows:
                        row_dict = dict(zip(columns, row))
                        
                        # Проверяем, существует ли запись
                        existing = db.session.get(Model, row_dict['id'])
                        if existing:
                            print(f"   ⏭️  Запись {row_dict['id']} уже существует, пропускаем")
                            continue
                        
                        # Создаем объект модели
                        obj = Model()
                        for key, value in row_dict.items():
                            if hasattr(obj, key):
                                setattr(obj, key, value)
                        
                        db.session.add(obj)
                    
                    db.session.commit()
                    
                    # Обновляем sequence для PostgreSQL
                    max_id_result = db.session.execute(
                        text(f"SELECT MAX(id) FROM {table_name}")
                    ).scalar()
                    
                    if max_id_result:
                        db.session.execute(
                            text(f"SELECT setval('{table_name}_id_seq', {max_id_result}, true)")
                        )
                        db.session.commit()
                
                print(f"   ✅ Успешно мигрировано: {len(rows)} записей")
                
            except Exception as e:
                print(f"   ❌ Ошибка при миграции {table_name}: {e}")
                continue
        
        print("\n" + "=" * 50)
        print("🎉 Миграция завершена!")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        sqlite_session.close()
        postgres_session.close()


def export_to_json():
    """Экспорт данных в JSON (альтернативный способ миграции)"""
    import json
    
    sqlite_url = os.getenv('SQLITE_DATABASE_URL', 'sqlite:///logistics.db')
    sqlite_engine = create_engine(sqlite_url)
    
    SQLiteSession = sessionmaker(bind=sqlite_engine)
    session = SQLiteSession()
    
    tables = ['users', 'points', 'couriers', 'routes', 'orders']
    data = {}
    
    print("📤 Экспорт данных в JSON...")
    
    for table in tables:
        try:
            result = session.execute(text(f"SELECT * FROM {table}"))
            rows = result.fetchall()
            columns = list(result.keys())
            
            data[table] = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # Конвертируем datetime в строку
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    row_dict[col] = value
                data[table].append(row_dict)
            
            print(f"   ✅ {table}: {len(rows)} записей")
            
        except Exception as e:
            print(f"   ❌ {table}: {e}")
    
    # Сохраняем в файл
    output_file = 'database_export.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Данные экспортированы в {output_file}")
    session.close()
    return output_file


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Миграция данных из SQLite в PostgreSQL')
    parser.add_argument('--export', action='store_true', help='Только экспорт в JSON')
    parser.add_argument('--migrate', action='store_true', help='Полная миграция в PostgreSQL')
    
    args = parser.parse_args()
    
    if args.export:
        export_to_json()
    elif args.migrate:
        migrate_data()
    else:
        print("yo.route - Инструмент миграции базы данных")
        print("=" * 50)
        print("\nИспользование:")
        print("  python migrate_to_postgres.py --export   # Экспорт в JSON")
        print("  python migrate_to_postgres.py --migrate  # Миграция в PostgreSQL")
        print("\nПеременные окружения:")
        print("  SQLITE_DATABASE_URL  - URL SQLite базы (по умолчанию: sqlite:///logistics.db)")
        print("  DATABASE_URL         - URL PostgreSQL базы (обязательно для --migrate)")
