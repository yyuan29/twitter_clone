from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

import sqlite3
import os
import re
import html
from datetime import datetime

# -----------------------
# APP SETUP
# -----------------------
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


# -----------------------
# SAFE LINKIFY
# -----------------------
def linkify(text):
    if not text:
        return ""

    text = html.escape(str(text))

    return re.sub(
        r'(https?://[^\s]+)',
        r'<a href="\1" target="_blank">\1</a>',
        text
    )

templates.env.globals["linkify"] = linkify


# -----------------------
# DB
# -----------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # This line is the "Safety Net"
    # It creates the table immediately if it's missing
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            edited_at TEXT
        )
    ''')
    conn.commit()
    return conn

# -----------------------
# HOME
# -----------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = get_db()
    messages_list = [] # Initialize so IDE is happy
    
    query = '''
        SELECT 
            messages.id, 
            messages.content, 
            messages.timestamp, 
            messages.user_id, 
            messages.edited_at,
            users.username, 
            users.age
        FROM messages
        JOIN users ON messages.user_id = users.id
        ORDER BY messages.timestamp DESC
    '''
    
    try:
        rows = db.execute(query).fetchall()
        messages_list = [dict(row) for row in rows]
    except sqlite3.OperationalError as e:
        # If the table is missing, we catch it here
        print(f"Table Error: {e}")
        messages_list = [] 
    finally:
        db.close()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "messages": messages_list,
            "user": request.cookies.get("username")
        }
    )


# -----------------------
# LOGIN
# -----------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
    request=request, 
    name="login.html", 
    context={"request": request}
)

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password)
    ).fetchone()
    conn.close()

    if not user:
        return HTMLResponse("Invalid login", 401)

    resp = RedirectResponse("/", 303)
    resp.set_cookie("username", username)
    resp.set_cookie("user_id", str(user["id"]))
    return resp


# -----------------------
# LOGOUT
# -----------------------
@app.get("/logout")
async def logout():
    resp = RedirectResponse("/", 303)
    resp.delete_cookie("username")
    resp.delete_cookie("user_id")
    return resp

# -----------------------
# REGISTER
# -----------------------
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"request": request}
    )

@app.post("/register")
async def register_user(
    username: str = Form(...), 
    password: str = Form(...), 
    age: int = Form(...)
):
    db = get_db()
    try:
        # SAFETY CHECK: Create the table if it somehow vanished
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                age INTEGER NOT NULL
            )
        ''')

        # Now do the insert
        db.execute(
            "INSERT INTO users (username, password, age) VALUES (?, ?, ?)",
            (username, password, age)
        )
        db.commit()
        
        return RedirectResponse(url="/login", status_code=303)

    except sqlite3.IntegrityError:
        return HTMLResponse(content="Username already exists!", status_code=400)
    except Exception as e:
        # This will tell us exactly what the database is complaining about
        return HTMLResponse(content=f"Database Error: {e}", status_code=500)
    finally:
        db.close()


# -----------------------
# CREATE MESSAGE
# -----------------------
@app.get("/create_message", response_class=HTMLResponse)
async def create_message_page(request: Request):
    # Check if the user is logged in before showing the form
    if not request.cookies.get("user_id"):
        return RedirectResponse("/login", status_code=303)
        
    return templates.TemplateResponse(
        request=request,
        name="create_message.html", 
        context={"request": request}
    )

@app.post("/create_message")
async def create_message(request: Request, content: str = Form(...)):
    user_id = request.cookies.get("user_id")

    # If no cookie, send them to login
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    # Use the same function name we used in the index route
    db = get_db() 
    try:
        db.execute(
            "INSERT INTO messages (user_id, content) VALUES (?, ?)",
            (int(user_id), content) # Ensure user_id is an integer for the DB
        )
        db.commit()
    except Exception as e:
        print(f"Error saving message: {e}")
    finally:
        db.close()

    return RedirectResponse("/", status_code=303)

# -----------------------
# DELETE MESSAGE
# -----------------------
@app.get("/delete_message/{msg_id}")
async def delete(msg_id: int, request: Request):
    user_id = request.cookies.get("user_id")

    if not user_id:
        return RedirectResponse("/login", status_code=303)

    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM messages WHERE id=? AND user_id=?",
            (msg_id, int(user_id))
        )
        conn.commit()
    except Exception as e:
        print(f"Delete Error: {e}")
    finally:
        conn.close()

    return RedirectResponse("/", status_code=303)

# -----------------------
# EDIT MESSAGE
# -----------------------
@app.get("/edit_message/{msg_id}", response_class=HTMLResponse)
async def edit_message_page(msg_id: int, request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    db = get_db()
    message = db.execute(
        "SELECT * FROM messages WHERE id=? AND user_id=?", 
        (msg_id, user_id)
    ).fetchone()
    db.close()

    if not message:
        return HTMLResponse("Message not found or unauthorized", status_code=404)

    return templates.TemplateResponse(
        request=request,
        name="edit_message.html",
        context={"request": request, "message": message}
    )

@app.post("/edit_message/{msg_id}")
async def edit_message_submit(msg_id: int, request: Request, content: str = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    db = get_db()
    try:
        db.execute("""
            UPDATE messages
            SET content=?, edited_at=?
            WHERE id=? AND user_id=?
        """, (
            content,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            msg_id,
            user_id
        ))
        db.commit()
    finally:
        db.close()

    return RedirectResponse("/", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)