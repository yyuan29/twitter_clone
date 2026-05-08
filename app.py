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

# Mount static folder for logo.png
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

# -----------------------
# SAFE LINKIFY (EXTRA CREDIT)
# -----------------------
def linkify(text):
    if not text:
        return ""
    text = html.escape(str(text))
    return re.sub(
        r'(https?://[^\s]+|www\.[^\s]+)',
        lambda m: f'<a href="{"http://" if m.group(0).startswith("www") else ""}{m.group(0)}" target="_blank">{m.group(0)}</a>',
        text
    )

templates.env.globals["linkify"] = linkify

# -----------------------
# DATABASE CONFIG
# -----------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            age INTEGER NOT NULL
        )
    ''')
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
# HOME FEED
# -----------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    db = get_db()
    query = '''
        SELECT messages.id, messages.content, messages.timestamp, 
               messages.user_id, messages.edited_at, users.username, users.age
        FROM messages
        LEFT JOIN users ON messages.user_id = users.id
        ORDER BY messages.timestamp DESC
    '''
    rows = db.execute(query).fetchall()
    messages_list = [dict(row) for row in rows]
    db.close()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "messages": messages_list,
            "user": request.cookies.get("username")
        }
    )

# -----------------------
# LOGIN / LOGOUT
# -----------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
    conn.close()
    
    if not user:
        return HTMLResponse("Invalid login. <a href='/login'>Try again</a>", 401)
    
    resp = RedirectResponse("/", 303)
    resp.set_cookie("username", username)
    resp.set_cookie("user_id", str(user["id"]))
    return resp

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
    return templates.TemplateResponse(request=request, name="register.html", context={})

@app.post("/register")
async def register_user(username: str = Form(...), password: str = Form(...), 
                        confirm_password: str = Form(...), age: int = Form(...)):
    if password != confirm_password:
        return HTMLResponse("Passwords do not match!", 400)
    
    db = get_db()
    try:
        cursor = db.execute("INSERT INTO users (username, password, age) VALUES (?, ?, ?)", (username, password, age))
        db.commit()
        new_id = cursor.lastrowid
        
        resp = RedirectResponse(url="/", status_code=303)
        resp.set_cookie("username", username)
        resp.set_cookie("user_id", str(new_id))
        return resp
    except sqlite3.IntegrityError:
        return HTMLResponse("Username taken!", 400)
    finally:
        db.close()

# -----------------------
# MESSAGES (CREATE / EDIT / DELETE)
# -----------------------
@app.get("/create_message", response_class=HTMLResponse)
async def create_message_page(request: Request):
    if not request.cookies.get("user_id"): return RedirectResponse("/login", 303)
    return templates.TemplateResponse(request=request, name="create_message.html", context={})

@app.post("/create_message")
async def create_message(request: Request, content: str = Form(...)):
    user_id = request.cookies.get("user_id")
    if not user_id: return RedirectResponse("/login", 303)
    
    db = get_db() 
    db.execute("INSERT INTO messages (user_id, content) VALUES (?, ?)", (int(user_id), content))
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

@app.get("/edit_message/{msg_id}", response_class=HTMLResponse)
async def edit_message_page(msg_id: int, request: Request):
    user_id = request.cookies.get("user_id")
    db = get_db()
    message = db.execute("SELECT * FROM messages WHERE id=? AND user_id=?", (msg_id, user_id)).fetchone()
    db.close()
    
    if not message: return HTMLResponse("Unauthorized", 403)
    return templates.TemplateResponse(request=request, name="edit_message.html", context={"message": message})

@app.post("/edit_message/{msg_id}")
async def edit_message_submit(msg_id: int, request: Request, content: str = Form(...)):
    user_id = request.cookies.get("user_id")
    db = get_db()
    db.execute("UPDATE messages SET content=?, edited_at=? WHERE id=? AND user_id=?",
               (content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg_id, user_id))
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

@app.get("/delete_message/{msg_id}")
async def delete_msg(msg_id: int, request: Request):
    user_id = request.cookies.get("user_id")
    db = get_db()
    db.execute("DELETE FROM messages WHERE id=? AND user_id=?", (msg_id, user_id))
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

# -----------------------
# ACCOUNT MANAGEMENT
# -----------------------
@app.get("/delete_account")
async def delete_account(request: Request):
    user_id = request.cookies.get("user_id")
    if not user_id: return RedirectResponse("/login", 303)
    
    db = get_db()
    db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    db.close()
    
    resp = RedirectResponse("/", 303)
    resp.delete_cookie("username")
    resp.delete_cookie("user_id")
    return resp

@app.get("/reset_password", response_class=HTMLResponse)
async def reset_page(request: Request):
    if not request.cookies.get("user_id"): return RedirectResponse("/login", 303)
    return templates.TemplateResponse(request=request, name="reset_password.html", context={})

@app.post("/reset_password")
async def reset_submit(request: Request, old_password: str = Form(...), new_password: str = Form(...), confirm_new_password: str = Form(...)):
    user_id = request.cookies.get("user_id")
    if new_password != confirm_new_password: return HTMLResponse("Passwords mismatch", 400)
    
    db = get_db()
    user = db.execute("SELECT password FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user or user["password"] != old_password:
        db.close()
        return HTMLResponse("Old password wrong", 403)
        
    db.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

# -----------------------
# JSON API
# -----------------------
@app.get("/api/messages")
async def get_messages_json():
    db = get_db()
    query = '''
        SELECT messages.id, messages.content, messages.timestamp, 
               messages.user_id, messages.edited_at, users.username
        FROM messages
        LEFT JOIN users ON messages.user_id = users.id
        ORDER BY messages.timestamp DESC
    '''
    rows = db.execute(query).fetchall()
    messages_list = [dict(row) for row in rows]
    db.close()
    
    return {
        "status": "success",
        "count": len(messages_list),
        "data": messages_list
    }

# -----------------------
# SERVER START
# -----------------------
if __name__ == "__main__":
    import uvicorn
    # Back to local-only for stability
    uvicorn.run(app, host="127.0.0.1", port=8000)