"""
Migration: Add Telegram integration fields to User model
Adds telegram_chat_id and auth_code columns to users table

Run this script to update existing database schema:
    python migrate_user_telegram.py
"""

import os
import sys

# Add project directory to path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from app import app
from models import db

def migrate():
    """Add telegram_chat_id and auth_code columns to users table"""
    
    with app.app_context():
        # Check database type
        database_url = app.config['SQLALCHEMY_DATABASE_URI']
        
        if 'sqlite' in database_url:
            # SQLite migration
            from sqlalchemy import text
            
            # Check if columns already exist
            result = db.session.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'telegram_chat_id' not in columns:
                print("Adding telegram_chat_id column to users table...")
                db.session.execute(text(
                    "ALTER TABLE users ADD COLUMN telegram_chat_id VARCHAR(50)"
                ))
                print("✅ telegram_chat_id column added")
            else:
                print("ℹ️  telegram_chat_id column already exists")
            
            if 'auth_code' not in columns:
                print("Adding auth_code column to users table...")
                db.session.execute(text(
                    "ALTER TABLE users ADD COLUMN auth_code VARCHAR(20) UNIQUE"
                ))
                print("✅ auth_code column added")
            else:
                print("ℹ️  auth_code column already exists")
                
        elif 'postgresql' in database_url:
            # PostgreSQL migration
            from sqlalchemy import text
            
            # Check if columns exist
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'users'
            """))
            columns = [row[0] for row in result.fetchall()]
            
            if 'telegram_chat_id' not in columns:
                print("Adding telegram_chat_id column to users table...")
                db.session.execute(text(
                    "ALTER TABLE users ADD COLUMN telegram_chat_id VARCHAR(50)"
                ))
                print("✅ telegram_chat_id column added")
            else:
                print("ℹ️  telegram_chat_id column already exists")
            
            if 'auth_code' not in columns:
                print("Adding auth_code column to users table...")
                db.session.execute(text(
                    "ALTER TABLE users ADD COLUMN auth_code VARCHAR(20) UNIQUE"
                ))
                print("✅ auth_code column added")
            else:
                print("ℹ️  auth_code column already exists")
        
        db.session.commit()
        print("\n✅ Migration completed successfully!")


if __name__ == '__main__':
    print("🔄 Running User Telegram fields migration...")
    print("=" * 50)
    migrate()
