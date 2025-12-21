"""Reset database schema on Railway PostgreSQL"""
import os
import sys

# Для внешних подключений используем PUBLIC URL
DATABASE_URL = os.getenv('DATABASE_PUBLIC_URL') or os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ DATABASE_URL not found. Run with: railway run python3 reset_db.py")
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2...")
    os.system('pip install psycopg2-binary')
    import psycopg2

print(f"🔗 Connecting to PostgreSQL...")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

print("🗑️ Dropping all tables...")
cursor.execute("DROP SCHEMA public CASCADE;")
cursor.execute("CREATE SCHEMA public;")

cursor.close()
conn.close()

print("✅ Database reset complete! Tables will be recreated on next deploy.")
