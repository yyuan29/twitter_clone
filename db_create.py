import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, age INTEGER)')
cursor.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, user_id INTEGER, content TEXT, timestamp DATETIME)')

# Seed data
cursor.execute('INSERT INTO users (username, age) VALUES ("Alice", 25), ("Bob", 30)')
cursor.execute('INSERT INTO messages (user_id, content, timestamp) VALUES (1, "Hello World!", "2023-10-01 10:00:00")')
cursor.execute('INSERT INTO messages (user_id, content, timestamp) VALUES (2, "Flask is fun.", "2023-10-01 11:00:00")')

conn.commit()
conn.close()