import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "database.db"

# Sample data for random generation
adjectives = ["Happy", "Sad", "Blue", "Fast", "Shiny", "Grumpy", "Epic", "Wild"]
nouns = ["Bird", "Chirper", "Falcon", "Coder", "Pizza", "Eagle", "Skywalker", "Pilot"]
contents = [
    "Just had the best coffee! ☕",
    "Coding my Twitter clone today. #Python",
    "Has anyone seen the new movie?",
    "Birdie is way better than the other apps.",
    "The weather is amazing right now!",
    "Just reached 100 followers! Thanks everyone.",
    "Learning FastAPI is actually pretty fun.",
    "Standardized test tomorrow... wish me luck.",
    "Does anyone have a good cookie recipe?",
    "Just posted a new photo on my profile!"
]

def populate_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Cleaning old data...")
    cursor.execute("DELETE FROM messages")
    cursor.execute("DELETE FROM users")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='messages' OR name='users'")

    print("Generating 200 users...")
    user_list = []
    for i in range(1, 201):
        username = f"{random.choice(adjectives)}{random.choice(nouns)}{i}"
        password = "password123"
        age = random.randint(13, 80)
        bio = f"Hi, I am Birdie user #{i}! I love coding and birds."
        user_list.append((username, password, age, bio))
    
    cursor.executemany("INSERT INTO users (username, password, age, bio) VALUES (?, ?, ?, ?)", user_list)
    
    # Get all user IDs
    cursor.execute("SELECT id FROM users")
    user_ids = [row[0] for row in cursor.fetchall()]

    print("Generating 40,000 messages (200 per user)...")
    message_list = []
    base_time = datetime.now()

    for u_id in user_ids:
        for m_idx in range(200):
            content = random.choice(contents)
            # Create random timestamps over the last 30 days
            timestamp = base_time - timedelta(minutes=random.randint(0, 43200))
            message_list.append((u_id, content, timestamp.strftime("%Y-%m-%d %H:%M:%S")))

    cursor.executemany("INSERT INTO messages (user_id, content, timestamp) VALUES (?, ?, ?)", message_list)
    
    conn.commit()
    conn.close()
    print("Successfully populated 200 users and 40,000 messages!")

if __name__ == "__main__":
    populate_data()