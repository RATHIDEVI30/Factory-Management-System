import sqlite3
import os

db_path = os.path.join('instance', 'kks_factory.db')

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check existing columns in contact table
cursor.execute("PRAGMA table_info(contact)")
columns = [info[1] for info in cursor.fetchall()]

print(f"Current columns in 'contact' table: {columns}")

new_columns = {
    'reply': 'TEXT',
    'reply_date': 'DATETIME',
    'status': "VARCHAR(20) DEFAULT 'New'",
    'phone': "VARCHAR(20) DEFAULT ''",
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

# Check existing columns in system_config table and add smtp fields if needed
cursor.execute("SELECT key FROM system_config")
existing_keys = [row[0] for row in cursor.fetchall()]
print(f"\nExisting system_config keys: {existing_keys}")

new_configs = {
    'smtp_email': '',
    'smtp_password': '',
}

for key, value in new_configs.items():
    if key not in existing_keys:
        try:
            print(f"Adding system_config key '{key}'...")
            cursor.execute("INSERT INTO system_config (key, value) VALUES (?, ?)", (key, value))
            print(f"Successfully added '{key}'.")
        except Exception as e:
            print(f"Error adding '{key}': {e}")
    else:
        print(f"Config key '{key}' already exists.")

conn.commit()
conn.close()
print("\nDatabase update completed.")
