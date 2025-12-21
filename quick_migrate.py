"""Quick migration for Railway PostgreSQL"""
from app import app, db
from sqlalchemy import text

with app.app_context():
    print("Running migration on Railway PostgreSQL...")
    
    # User columns
    db.session.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(50)'))
    db.session.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_code VARCHAR(20)'))
    
    # Order columns for production logistics
    db.session.execute(text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS type VARCHAR(20) DEFAULT 'delivery'"))
    db.session.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS required_courier_id INTEGER REFERENCES couriers(id)'))
    db.session.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS time_window_start VARCHAR(5)'))
    db.session.execute(text('ALTER TABLE orders ADD COLUMN IF NOT EXISTS time_window_end VARCHAR(5)'))
    
    # Create user_settings table if not exists
    db.session.execute(text('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE NOT NULL REFERENCES users(id),
            theme VARCHAR(20) DEFAULT 'light',
            default_page VARCHAR(50) DEFAULT 'orders',
            planning_mode VARCHAR(20) DEFAULT 'manual',
            courier_notifications VARCHAR(10) DEFAULT 'off',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    '''))
    
    db.session.commit()
    print("Done! All tables and columns created successfully.")
