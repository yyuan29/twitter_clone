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

# Make sure you have a folder named 'static'
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

# --- UTILS ---
def linkify(text):
    if not text: return ""
    text = html.escape(str(text))
    return re.sub(r'(https?://[^\s]+|www\.[^\s]+)', 
                  lambda m: f'<a href="{"http://" if m.group(0).startswith("www") else ""}{m.group(0)}" target="_blank">{m.group(0)}</a>', 
                  text)

templates.env.globals["linkify"] = linkify

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Ensure tables exist
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, age INTEGER, bio TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, edited_at TEXT)')
    
    # Auto-fix: Add bio column to old databases if it's missing
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'bio' not in columns:
        conn.execute('ALTER TABLE users ADD COLUMN bio TEXT')
    
    conn.commit()
    return conn

# -----------------------
# HOME FEED (WITH PAGINATION)
# -----------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, page: int = 1):
    # Ensure page is at least 1
    if page < 1: 
        page = 1
        
    limit = 50
    offset = (page - 1) * limit
    
    db = get_db()
    
    # 1. Get the total count of messages to calculate if there is a "Next" page
    total_messages = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    
    # 2. Fetch only 50 messages for the current page
    query = f'''
        SELECT messages.*, users.username, users.age FROM messages
        LEFT JOIN users ON messages.user_id = users.id
        ORDER BY messages.timestamp DESC 
        LIMIT {limit} OFFSET {offset}
    '''
    msgs = db.execute(query).fetchall()
    db.close()
    
    # Determine if buttons should be shown
    has_next = (offset + limit) < total_messages
    has_prev = page > 1
    
    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={
            "request": request, 
            "messages": msgs, 
            "user": request.cookies.get("username"),
            "page": page,
            "has_next": has_next,
            "has_prev": has_prev
        }
    )

# -----------------------
# AUTH ROUTES (LOGIN/REGISTER)
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
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
    db.close()
    if not user: return HTMLResponse("Invalid login. <a href='/login'>Try again</a>", 401)
    
    resp = RedirectResponse("/", 303)
    resp.set_cookie("username", username)
    resp.set_cookie("user_id", str(user["id"]))
    return resp

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html", 
        context={"request": request}
    )

@app.post("/register")
async def register_user(username: str = Form(...), password: str = Form(...), confirm_password: str = Form(...), age: int = Form(...)):
    if password != confirm_password: return HTMLResponse("Passwords mismatch", 400)
    db = get_db()
    try:
        # We include a blank bio "" so the new account is ready
        cursor = db.execute("INSERT INTO users (username, password, age, bio) VALUES (?, ?, ?, ?)", (username, password, age, ""))
        db.commit()
        resp = RedirectResponse("/", 303)
        resp.set_cookie("username", username)
        resp.set_cookie("user_id", str(cursor.lastrowid))
        return resp
    except sqlite3.IntegrityError: return HTMLResponse("Username taken!", 400)
    finally: db.close()

@app.get("/logout")
async def logout():
    resp = RedirectResponse("/", 303)
    resp.delete_cookie("username")
    resp.delete_cookie("user_id")
    return resp

# -----------------------
# PROFILE & BIO ROUTES
# -----------------------
@app.get("/profile/{username}", response_class=HTMLResponse)
async def view_profile(request: Request, username: str):
    db = get_db()
    user_data = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user_data:
        db.close()
        return HTMLResponse("User not found", 404)
    
    msgs = db.execute('SELECT * FROM messages WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10', (user_data['id'],)).fetchall()
    db.close()
    
    return templates.TemplateResponse(
        name="profile.html", 
        context={
            "request": request, 
            "profile_user": user_data, 
            "messages": msgs,
            "is_own_profile": request.cookies.get("username") == username, 
            "user": request.cookies.get("username")
        }
    )

@app.post("/update_profile")
async def update_profile(request: Request, bio: str = Form(...)):
    username = request.cookies.get("username")
    if not username: return RedirectResponse("/login", 303)
    db = get_db()
    db.execute("UPDATE users SET bio = ? WHERE username = ?", (bio, username))
    db.commit()
    db.close()
    return RedirectResponse(f"/profile/{username}", 303)

# -----------------------
# MESSAGE ROUTES
# -----------------------
@app.get("/create_message", response_class=HTMLResponse)
async def create_message_page(request: Request):
    if not request.cookies.get("user_id"): return RedirectResponse("/login", 303)
    return templates.TemplateResponse(
        request=request,
        name="create_message.html", 
        context={"request": request}
    )

@app.post("/create_message")
async def create_message(request: Request, content: str = Form(...)):
    u_id = request.cookies.get("user_id")
    if not u_id: return RedirectResponse("/login", 303)
    db = get_db()
    db.execute("INSERT INTO messages (user_id, content) VALUES (?, ?)", (int(u_id), content))
    db.commit(); db.close()
    return RedirectResponse("/", 303)

# --- DELETE MESSAGE ---
@app.get("/delete_message/{msg_id}")
async def delete_msg(msg_id: int, request: Request):
    u_id = request.cookies.get("user_id")
    if not u_id: return RedirectResponse("/login", 303)
    
    db = get_db()
    # Ensure only the owner can delete their message
    db.execute("DELETE FROM messages WHERE id=? AND user_id=?", (msg_id, int(u_id)))
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

# --- EDIT MESSAGE ---
@app.get("/edit_message/{msg_id}", response_class=HTMLResponse)
async def edit_message_page(request: Request, msg_id: int):
    u_id = request.cookies.get("user_id")
    if not u_id: return RedirectResponse("/login", 303)
    
    db = get_db()
    msg = db.execute("SELECT * FROM messages WHERE id=? AND user_id=?", (msg_id, int(u_id))).fetchone()
    db.close()
    
    if not msg: return HTMLResponse("Message not found or unauthorized", 404)
    
    return templates.TemplateResponse(
        request=request,
        name="edit_message.html", 
        context={"request": request, "message": msg, "user": request.cookies.get("username")}
    )

@app.post("/edit_message/{msg_id}")
async def edit_message_submit(msg_id: int, request: Request, content: str = Form(...)):
    u_id = request.cookies.get("user_id")
    if not u_id: return RedirectResponse("/login", 303)
    
    db = get_db()
    db.execute("UPDATE messages SET content=?, edited_at=? WHERE id=? AND user_id=?", 
               (content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg_id, int(u_id)))
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)