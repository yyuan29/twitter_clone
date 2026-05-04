from flask import Flask, render_template, url_for
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

@app.route('/')
def index():
    """
    Fetches messages joined with user data, sorted by newest first.
    Requirement 2 implementation.
    """
    conn = get_db_connection()
    # Joining tables to get username and age alongside the message
    query = '''
        SELECT messages.content, messages.timestamp, users.username, users.age
        FROM messages
        JOIN users ON messages.user_id = users.id
        ORDER BY messages.timestamp DESC
    '''
    messages_rows = conn.execute(query).fetchall()
    conn.close()

    # Convert rows to a list of dictionaries (Step 1 of Hint)
    messages_list = []
    for row in messages_rows:
        messages_list.append({
            'text': row['content'],
            'timestamp': row['timestamp'],
            'username': row['username'],
            'age': row['age']
        })

    return render_template('index.html', messages=messages_list)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/logout')
def logout():
    return render_template('logout.html')

@app.route('/create_message')
def create_message():
    return render_template('create_message.html')

@app.route('/create_user')
def create_user():
    return render_template('create_user.html')

if __name__ == '__main__':
    app.run(debug=True)