import sqlite3
import os

db_path = os.path.join('instance', 'kks_factory.db')

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check existing columns
cursor.execute("PRAGMA table_info(contact)")
columns = [info[1] for info in cursor.fetchall()]

print(f"Current columns in 'contact' table: {columns}")

new_columns = {
    'reply': 'TEXT',
    'reply_date': 'DATETIME',
    'status': "VARCHAR(20) DEFAULT 'New'"
}

for col, col_type in new_columns.items():
    if col not in columns:
        try:
            print(f"Adding column '{col}'...")
            cursor.execute(f"ALTER TABLE contact ADD COLUMN {col} {col_type}")
            print(f"Successfully added '{col}'.")
        except Exception as e:
            print(f"Error adding '{col}': {e}")
    else:
        print(f"Column '{col}' already exists.")

conn.commit()
conn.close()
print("Database update completed.")
