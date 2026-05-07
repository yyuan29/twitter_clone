import sqlite3
import random

def populate():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    print("Generating 200 users...")
    for i in range(2, 202): # Start at 2 because admin is 1
        username = f"user_{i}"
        c.execute("INSERT OR IGNORE INTO users (id, username, password, age) VALUES (?, ?, ?, ?)", 
                  (i, username, "pass", random.randint(18, 80)))
        
        if i % 10 == 0: print(f"Created {i} users...")
        
        # 200 messages per user
        for j in range(200):
            content = f"Random message {j} from {username}. Check out http://google.com!"
            c.execute("INSERT INTO messages (user_id, content) VALUES (?, ?)", (i, content))
            
    conn.commit()
    conn.close()
    print("Done! 40,000 messages created.")

if __name__ == "__main__":
    populate()