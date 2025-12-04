"""
Migration script to add new fields to the database.
Run this script to add:
- courier_id, point_id to orders table
- vehicle_type to couriers table
"""

import sqlite3
import os

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'logistics.db')

def migrate():
    print(f"🔄 Running migration on: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print("❌ Database file not found. It will be created when you run the app.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check and add columns to orders table
    print("📦 Checking orders table...")
    cursor.execute("PRAGMA table_info(orders)")
    order_columns = [col[1] for col in cursor.fetchall()]
    
    if 'courier_id' not in order_columns:
        print("  ➕ Adding courier_id column to orders")
        cursor.execute("ALTER TABLE orders ADD COLUMN courier_id INTEGER REFERENCES couriers(id)")
    else:
        print("  ✓ courier_id already exists")
    
    if 'point_id' not in order_columns:
        print("  ➕ Adding point_id column to orders")
        cursor.execute("ALTER TABLE orders ADD COLUMN point_id INTEGER REFERENCES points(id)")
    else:
        print("  ✓ point_id already exists")
    
    # Check and add columns to couriers table
    print("👤 Checking couriers table...")
    cursor.execute("PRAGMA table_info(couriers)")
    courier_columns = [col[1] for col in cursor.fetchall()]
    
    if 'vehicle_type' not in courier_columns:
        print("  ➕ Adding vehicle_type column to couriers")
        cursor.execute("ALTER TABLE couriers ADD COLUMN vehicle_type VARCHAR(50) DEFAULT 'car'")
    else:
        print("  ✓ vehicle_type already exists")
    
    conn.commit()
    conn.close()
    
    print("✅ Migration completed successfully!")

if __name__ == '__main__':
    migrate()
