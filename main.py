import sqlite3
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()
# This middleware allows the 'request.session' to work
app.add_middleware(SessionMiddleware, secret_key="school_project")
templates = Jinja2Templates(directory="templates")

def get_db():
    """Connects to the database and ensures tables exist."""
    db = sqlite3.connect("twitter.db")
    db.row_factory = sqlite3.Row
    # Create tables if they aren't there yet
    db.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        username TEXT UNIQUE, 
        password TEXT)''')
    db.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        content TEXT, 
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    return db

# --- DOCTEST ---
def is_match(p1, p2):
    """
    Checks if two passwords match.
    >>> is_match("pass", "pass")
    True
    >>> is_match("pass", "fail")
    False
    """
    return p1 == p2

# --- ROUTES ---

@app.get("/")
def home(request: Request):
    db = get_db()
    # JOIN links the message to the user who wrote it
    # ORDER BY timestamp DESC puts newest messages at the top
    posts = db.execute('''
        SELECT m.content, m.timestamp, u.username 
        FROM messages m JOIN users u ON m.user_id = u.id 
        ORDER BY m.timestamp DESC
    ''').fetchall()
    db.close()
    return templates.TemplateResponse(request=request, name="home.html", context={"posts": posts})

@app.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse(request=request, name="signup.html")

@app.post("/signup")
def do_signup(u: str = Form(...), p1: str = Form(...), p2: str = Form(...)):
    if not is_match(p1, p2): 
        return "Error: Passwords do not match. Go back and try again."
    
    db = get_db()
    try:
        # Parameterized query (?) prevents SQL Injection (Requirement check!)
        db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (u, p1))
        db.commit()
        return RedirectResponse(url="/login", status_code=303)
    except sqlite3.IntegrityError:
        return "Error: User exists already. Try a different name."
    finally:
        db.close()

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/login")
def do_login(request: Request, u: str = Form(...), p: str = Form(...)):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username=? AND password=?', (u, p)).fetchone()
    db.close()

    if user:
        # Create the session 'cookie'
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]
        return RedirectResponse(url="/", status_code=303)
    return "Error: Invalid credentials. Go back and try again."

@app.get("/logout")
def logout(request: Request):
    request.session.clear() # Requirement: Delete the cookies
    return RedirectResponse(url="/", status_code=303)

@app.get("/create")
def create_page(request: Request):
    # Requirement: only visible/accessible if logged in
    if "user_id" not in request.session: 
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="create.html")

@app.post("/create")
def do_create(request: Request, msg: str = Form(...)):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=303)
        
    db = get_db()
    db.execute('INSERT INTO messages (user_id, content) VALUES (?, ?)', 
              (request.session["user_id"], msg))
    db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

if __name__ == "__main__":
    import doctest
    doctest.testmod() # Runs the password match tests
    uvicorn.run("main:app", host="127.0.0.1", port=8888, reload=True)