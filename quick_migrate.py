"""Quick migration for Railway PostgreSQL"""
from app import app, db
from sqlalchemy import text

with app.app_context():
    print("Running migration on Railway PostgreSQL...")
    db.session.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(50)'))
    db.session.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_code VARCHAR(20)'))
    db.session.commit()
    print("Done! Columns added successfully.")
