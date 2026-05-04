import sqlite3
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()

# Requirement 3: Static files mounting
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(SessionMiddleware, secret_key="supersecretkey")
templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    db = get_db()
    messages = db.execute('''
        SELECT m.content, m.timestamp, u.username, u.age 
        FROM messages m JOIN users u ON m.user_id = u.id 
        ORDER BY m.timestamp DESC
    ''').fetchall()
    db.close()
    
    # Use this EXACT syntax:
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "messages": messages}
    )

def get_db():
    """Connects to SQLite and creates tables if they don't exist."""
    db = sqlite3.connect("twitter.db")
    db.row_factory = sqlite3.Row
    # Requirement 2: User table includes 'age'
    db.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        username TEXT UNIQUE, 
        password TEXT,
        age INTEGER)''')
    db.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_id INTEGER, 
        content TEXT, 
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    return db

# --- DOCTESTS (Requirement: Simple and Easy) ---
def validate_age(age):
    """
    Checks if an age is valid (greater than 0).
    >>> validate_age(25)
    True
    >>> validate_age(-5)
    False
    """
    return age > 0

# --- ROUTES (Requirement 1: All 5 routes present) ---

@app.get("/")
def route_index(request: Request):
    """Requirement 2: Displays messages with text, timestamp, user, and age."""
    db = get_db()
    query = '''
        SELECT m.content, m.timestamp, u.username, u.age 
        FROM messages m JOIN users u ON m.user_id = u.id 
        ORDER BY m.timestamp DESC
    '''
    messages = db.execute(query).fetchall()
    db.close()
    return templates.TemplateResponse("index.html", {"request": request, "messages": messages})

@app.get("/create_user")
def route_create_user(request: Request):
    return templates.TemplateResponse("create_user.html", {"request": request})

@app.post("/create_user")
def do_create_user(u: str = Form(...), p: str = Form(...), age: int = Form(...)):
    if not validate_age(age):
        return "Invalid age. Go back."
    db = get_db()
    try:
        db.execute('INSERT INTO users (username, password, age) VALUES (?, ?, ?)', (u, p, age))
        db.commit()
        return RedirectResponse(url="/login", status_code=303)
    except sqlite3.IntegrityError:
        return "User already exists."
    finally:
        db.close()

@app.get("/login")
def route_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def do_login(request: Request, u: str = Form(...), p: str = Form(...)):
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username=? AND password=?', (u, p)).fetchone()
    db.close()
    if user:
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]
        return RedirectResponse(url="/", status_code=303)
    return "Invalid credentials."

@app.get("/create_message")
def route_create_message(request: Request):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("create_message.html", {"request": request})

@app.post("/create_message")
def do_create_message(request: Request, content: str = Form(...)):
    if "user_id" not in request.session:
        return RedirectResponse(url="/login", status_code=303)
    db = get_db()
    db.execute('INSERT INTO messages (user_id, content) VALUES (?, ?)', 
              (request.session["user_id"], content))
    db.commit()
    db.close()
    return RedirectResponse(url="/", status_code=303)

@app.get("/logout")
def route_logout(request: Request):
    request.session.clear()
    return templates.TemplateResponse("logout.html", {"request": request})

if __name__ == "__main__":
    import doctest
    doctest.testmod()
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)