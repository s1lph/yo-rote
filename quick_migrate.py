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
    
    db.session.commit()
    print("Done! All columns added successfully.")
