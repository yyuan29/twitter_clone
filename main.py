import sqlite3
from flask import Flask, render_template, request, redirect, session, flash

app = Flask(__name__)
app.secret_key = 'simple_key' # Needed for cookies/sessions

def get_db():
    """Connects to the database and creates tables if they don't exist."""
    db = sqlite3.connect('twitter.db')
    db.row_factory = sqlite3.Row
    # Automatically create tables so you don't get 'OperationalError'
    db.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    return db

# --- DOCTESTS ---
def check_match(a, b):
    """
    Checks if two things match. Used for password confirmation.
    >>> check_match('123', '123')
    True
    >>> check_match('123', 'abc')
    False
    """
    return a == b

# --- ROUTES ---

@app.route('/')
def home():
    db = get_db()
    # Gets all messages + who wrote them, newest first
    posts = db.execute('SELECT m.*, u.username FROM messages m JOIN users u ON m.user_id = u.id ORDER BY m.timestamp DESC').fetchall()
    return render_template('home.html', posts=posts)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user, p1, p2 = request.form['u'], request.form['p1'], request.form['p2']
        if not check_match(p1, p2):
            flash("Passwords don't match!")
        else:
            db = get_db()
            try:
                db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (user, p1))
                db.commit()
                return redirect('/login')
            except sqlite3.IntegrityError:
                flash("User already exists!")
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user, pw = request.form['u'], request.form['p']
        db = get_db()
        found = db.execute('SELECT * FROM users WHERE username=? AND password=?', (user, pw)).fetchone()
        if found:
            session['user_id'] = found['id'] # Log them in
            return redirect('/')
        flash("Wrong login!")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear() # Deletes the cookie
    return redirect('/')

@app.route('/create', methods=['GET', 'POST'])
def create():
    if 'user_id' not in session: return redirect('/login')
    if request.method == 'POST':
        db = get_db()
        db.execute('INSERT INTO messages (user_id, content) VALUES (?, ?)', (session['user_id'], request.form['msg']))
        db.commit()
        return redirect('/')
    return render_template('create.html')

if __name__ == '__main__':
    import doctest
    doctest.testmod()
    app.run(debug=True, port=8888)