import sqlite3

DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # -----------------------
    # USERS TABLE
    # -----------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            age INTEGER
        )
    """)

    # -----------------------
    # MESSAGES TABLE
    # -----------------------
    # FIX: added parent_id because your app.py uses it
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            edited_at TEXT,
            parent_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------
    # INDEXES (optional but good practice)
    # -----------------------
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_user_id
        ON messages(user_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_parent_id
        ON messages(parent_id)
    """)

    conn.commit()
    conn.close()

    print("Database initialized successfully!")

if __name__ == "__main__":
    init_db()