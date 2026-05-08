import sqlite3

def setup():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Drop tables if they exist to start fresh (optional)
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("DROP TABLE IF EXISTS messages")

    # Create the users table with the age column
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            age INTEGER NOT NULL
        )
    ''')

    # Create the messages table
    cursor.execute('''
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            edited_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✨ Database wiped and rebuilt with 'users' and 'messages' tables!")

if __name__ == "__main__":
    setup()