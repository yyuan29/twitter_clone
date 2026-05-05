import sqlite3

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # Create tables
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, age INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, user_id INTEGER, FOREIGN KEY(user_id) REFERENCES users(id))')
    
    # Add dummy data so the / route isn't empty
    cursor.execute("INSERT INTO users (username, age) VALUES ('User1', 25)")
    cursor.execute("INSERT INTO messages (content, user_id) VALUES ('This is the first message!', 1)")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
