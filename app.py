from flask import Flask, render_template
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    # Requirement 2: Joining tables to get text, timestamp, username, and age
    query = '''
        SELECT messages.content, messages.timestamp, users.username, users.age
        FROM messages
        JOIN users ON messages.user_id = users.id
        ORDER BY messages.timestamp DESC
    '''
    rows = conn.execute(query).fetchall()
    conn.close()

    # Step 1: Create list of dictionaries
    messages_list = []
    for row in rows:
        messages_list.append({
            'text': row['content'],
            'timestamp': row['timestamp'],
            'username': row['username'],
            'age': row['age']
        })

    return render_template('index.html', messages=messages_list)

# Requirement 1: The other 4 routes
@app.route('/login')
def login(): return render_template('login.html')

@app.route('/logout')
def logout(): return render_template('logout.html')

@app.route('/create_message')
def create_message(): return render_template('create_message.html')

@app.route('/create_user')
def create_user(): return render_template('create_user.html')

if __name__ == '__main__':
    app.run(debug=True)