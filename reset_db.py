
import os
import sys


DATABASE_URL = os.getenv('DATABASE_PUBLIC_URL') or os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("DATABASE_URL not found. Run with: railway run python3 reset_db.py")
    sys.exit(1)

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2...")
    os.system('pip install psycopg2-binary')
    import psycopg2

print(f"Connecting to PostgreSQL...")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

print("Dropping schema with all types...")
cursor.execute("DROP SCHEMA public CASCADE;")
cursor.execute("CREATE SCHEMA public;")
cursor.execute("GRANT ALL ON SCHEMA public TO public;")
cursor.execute("GRANT ALL ON SCHEMA public TO CURRENT_USER;")

cursor.close()
conn.close()

print("Database reset complete! Redeploy to recreate tables.")

