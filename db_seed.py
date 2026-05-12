import sqlite3
import random
from datetime import datetime, timedelta

DB_NAME = "database.db"

USERNAMES = [
    "alex", "sam", "jordan", "taylor", "morgan",
    "casey", "drew", "riley", "jamie", "quinn"
]

TEMPLATES = [
    "Just finished studying for exams 😭",
    "Why is CS homework always this hard",
    "Coffee saved my life today",
    "I need more sleep lol",
    "FastAPI is actually kinda cool",
    "SQLite is surprisingly powerful",
    "debugging for 3 hours straight...",
    "why does this bug only happen at 2am",
    "midterm season is destroying me",
    "this project is actually fun",
    "I should be coding rn",
    "send help",
    "almost done with this assignment",
    "professor said this was 'easy' 💀",
    "why is everything breaking"
]

def random_time():
    start = datetime(2025, 1, 1)
    end = datetime(2026, 5, 11)
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def main():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 🚀 SPEED BOOST (important even for 40k)
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=OFF;")
    cursor.execute("PRAGMA temp_store=MEMORY;")

    # Clear old messages
    cursor.execute("DELETE FROM messages")

    # -----------------------
    # Ensure users exist
    # -----------------------
    cursor.execute("SELECT id, username FROM users")
    user_map = {row[1]: row[0] for row in cursor.fetchall()}

    for name in USERNAMES:
        if name not in user_map:
            cursor.execute(
                "INSERT INTO users (username, password, age) VALUES (?, ?, ?)",
                (name, "test", random.randint(18, 30))
            )
            user_map[name] = cursor.lastrowid

    conn.commit()
    print("Users ready.")

    # -----------------------
    # Generate messages
    # -----------------------
    TOTAL = 40_000
    BATCH_SIZE = 5_000

    batch = []

    print("Generating 40,000 messages...")

    for i in range(TOTAL):
        username = random.choice(USERNAMES)
        user_id = user_map[username]

        content = random.choice(TEMPLATES)
        timestamp = random_time().strftime("%Y-%m-%d %H:%M:%S")

        batch.append((user_id, content, timestamp))

        if len(batch) >= BATCH_SIZE:
            cursor.executemany("""
                INSERT INTO messages (user_id, content, timestamp)
                VALUES (?, ?, ?)
            """, batch)

            conn.commit()
            batch = []

            print(f"Inserted {i+1}/{TOTAL}")

    # insert leftover rows
    if batch:
        cursor.executemany("""
            INSERT INTO messages (user_id, content, timestamp)
            VALUES (?, ?, ?)
        """, batch)

    conn.commit()
    conn.close()

    print("DONE: 40,000 messages inserted.")

if __name__ == "__main__":
    main()