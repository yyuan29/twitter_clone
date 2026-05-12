import sqlite3
import os

DB_NAME = "database.db"

def ensure_schema():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    # make sure users table exists first (safe even if already created)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            age INTEGER,
            bio TEXT
        )
    """)

    # messages table (unchanged)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            edited_at TEXT,
            parent_id INTEGER DEFAULT NULL
        )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    ensure_schema()