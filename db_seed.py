import sqlite3
import random
from datetime import datetime, timedelta

# Configuration
DB_PATH = "database.db"
TOTAL_USERS = 200
MESSAGES_PER_USER = 200

# Random content generators
USERNAMES = ["BirdieFan", "TechGuy", "CodingQueen", "NatureLover", "CoffeeAddict", "PixelArt", "TravelBug", "DataWizard"]
ADJECTIVES = ["Amazing", "Quiet", "Super", "Fast", "Creative", "Wild", "Funny", "Epic"]
NOUNS = ["day", "code", "morning", "sunset", "project", "coffee", "adventure", "idea"]
EMOJIS = ["🐦", "💻", "☕️", "🚀", "🔥", "✨"]

def generate_random_message():
    content = f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)}! {random.choice(EMOJIS)}"
    # Randomly add a link for 20% of messages
    if random.random() < 0.2:
        content += f" Check this out: http://birdie.com/test-{random.randint(1,100)}"
    return content

def seed_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"--- Starting Bulk Seed: {TOTAL_USERS * MESSAGES_PER_USER} messages ---")

    # 1. Create Users
    user_ids = []
    for i in range(1, TOTAL_USERS + 1):
        username = f"{random.choice(USERNAMES)}_{i}_{random.randint(10,99)}"
        password = "password123"
        age = random.randint(18, 75)
        
        try:
            cursor.execute("INSERT INTO users (username, password, age) VALUES (?, ?, ?)", (username, password, age))
            user_ids.append(cursor.lastrowid)
        except sqlite3.IntegrityError:
            continue # Skip if username somehow duplicates

    print(f"Created {len(user_ids)} unique users.")

    # 2. Create Messages
    all_messages = []
    base_time = datetime.now()

    for u_id in user_ids:
        for m_idx in range(MESSAGES_PER_USER):
            content = generate_random_message()
            # Stagger timestamps so they aren't all at the exact same second
            timestamp = (base_time - timedelta(minutes=random.randint(1, 10000))).strftime("%Y-%m-%d %H:%M:%S")
            all_messages.append((u_id, content, timestamp))

    # 3. Bulk Insert (executemany is MUCH faster than individual inserts)
    cursor.executemany(
        "INSERT INTO messages (user_id, content, timestamp) VALUES (?, ?, ?)", 
        all_messages
    )

    conn.commit()
    conn.close()
    print("--- Seeding Complete! 40,000 chirps added. ---")

if __name__ == "__main__":
    seed_database()