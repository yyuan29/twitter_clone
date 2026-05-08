from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from passlib.hash import pbkdf2_sha256

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
    # 1. Escape HTML first for security
    text = html.escape(str(text))
    
    # 2. Linkify URLs (http/https/www)
    text = re.sub(r'(https?://[^\s]+|www\.[^\s]+)', 
                  lambda m: f'<a href="{"http://" if m.group(0).startswith("www") else ""}{m.group(0)}" target="_blank">{m.group(0)}</a>', 
                  text)
    
    # 3. Linkify @Mentions

    # This finds @ followed by alphanumeric characters and turns it into a link
    text = re.sub(r'@(\w+)', 
                  r'<a href="/profile/\1" class="mention">@\1</a>', 
                  text)
    
    return text

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
    
    conn.execute('CREATE VIRTUAL TABLE IF NOT EXISTS messages_search USING fts5(content, message_id UNINDEXED)')
    conn.execute('''CREATE TABLE IF NOT EXISTS likes 
                (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                 user_id INTEGER, 
                 message_id INTEGER, 
                 UNIQUE(user_id, message_id))''')
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

@app.get("/reset_password", response_class=HTMLResponse)
async def reset_password_page(request: Request):
    user = request.cookies.get("username")
    if not user:
        return RedirectResponse("/login", 303)
    return templates.TemplateResponse(request=request, name="reset_password.html", context={})

@app.post("/reset_password")
async def handle_reset_password(
    request: Request, 
    old_password: str = Form(...), 
    new_password: str = Form(...), 
    confirm_password: str = Form(...)
):
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse("/login", 303)

    # 1. Check if passwords match
    if new_password != confirm_password:
        return templates.TemplateResponse(
            request=request, name="reset_password.html", 
            context={"error": "New passwords do not match!"}
        )

    db = get_db()
    user_record = db.execute("SELECT password FROM users WHERE username = ?", (username,)).fetchone()

    # 2. Verify old password
    if not user_record or not pbkdf2_sha256.verify(old_password, user_record["password"]):
        db.close()
        return templates.TemplateResponse(
            request=request, 
            name="reset_password.html", 
            context=
            {"error": "Current password is incorrect."}
        )

    # 3. Hash and update
    new_hashed = pbkdf2_sha256.hash(new_password)
    db.execute("UPDATE users SET password = ? WHERE username = ?", (new_hashed, username))
    db.commit()
    db.close()

    # Success! Redirect to profile or home
    return RedirectResponse(f"/profile/{username}", 303)

# -----------------------
# PROFILE & BIO ROUTES
# -----------------------

@app.get("/profile/{username}", response_class=HTMLResponse)
async def view_profile(request: Request, username: str):
    db = get_db()
    # Use 'LIKE' to ensure 'Yyuan29' matches 'yyuan29'
    user_data = db.execute("SELECT * FROM users WHERE username LIKE ?", (username,)).fetchone()
    
    if not user_data:
        db.close()
        return HTMLResponse(f"User '{username}' not found", 404)
    
    # Get all messages for this specific user
    msgs = db.execute("SELECT * FROM messages WHERE user_id = ? ORDER BY timestamp DESC", (user_data['id'],)).fetchall()
    db.close()
    
    # Check if the person viewing the profile is the owner of the profile
    logged_in_user = request.cookies.get("username")
    is_own_profile = False
    if logged_in_user and logged_in_user.lower() == user_data['username'].lower():
        is_own_profile = True
    
    return templates.TemplateResponse(
        request=request,
        name="profile.html", 
        context={
            "request": request, 
            "profile_user": user_data, 
            "messages": msgs,
            "is_own_profile": is_own_profile,
            "user": logged_in_user
        }
    )

@app.post("/update_profile")
async def update_profile(request: Request, bio: str = Form(...)):
    # 1. Figure out who is logged in via the cookie
    username = request.cookies.get("username")
    
    if not username or username == "None":
        return RedirectResponse("/login", 303)
    
    # 2. Update the database
    db = get_db()
    db.execute("UPDATE users SET bio = ? WHERE username = ?", (bio, username))
    db.commit()
    db.close()
    
    # 3. Send them back to their profile to see the new bio
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

    # 1. Insert into main table
    cursor = db.execute("INSERT INTO messages (user_id, content) VALUES (?, ?)", (int(u_id), content))
    msg_id = cursor.lastrowid

    # 2. Insert into FTS5 search table
    db.execute("INSERT INTO messages_search (content, message_id) VALUES (?, ?)", (content, msg_id))

    db.execute("INSERT INTO messages (user_id, content) VALUES (?, ?)", (int(u_id), content))
    db.commit(); db.close()
    return RedirectResponse("/", 303)

@app.get("/search", response_class=HTMLResponse)
async def search_messages(request: Request, q: str = ""):
    db = get_db()
    
    # 1. Clean the query
    # Removing '@' ensures that searching '@yyuan29' finds the user 'yyuan29'
    clean_q = q.replace("@", "").strip()
    
    # If the search is empty, just send them home
    if not clean_q:
        db.close()
        return RedirectResponse("/", 303)

    # 2. Sync FTS5 (Maintenance Step)
    # If you just ran a population script, the search table might be empty.
    # This line ensures the search index has data to look through.
    count_search = db.execute("SELECT COUNT(*) FROM messages_search").fetchone()[0]
    if count_search == 0:
        db.execute("INSERT INTO messages_search(content, message_id) SELECT content, id FROM messages")
        db.commit()

    # 3. The "Smart Search" Query
    # We use UNION to avoid the "MATCH in requested context" error.
    # This finds: 
    #   - Messages containing the word (via FTS5)
    #   - Messages sent by a user whose name matches the query (via LIKE)
    query = """
        SELECT m.*, u.username, u.age 
        FROM messages m
        JOIN users u ON m.user_id = u.id
        WHERE m.id IN (
            SELECT message_id FROM messages_search WHERE messages_search MATCH ?
        )
        UNION
        SELECT m.*, u.username, u.age 
        FROM messages m
        JOIN users u ON m.user_id = u.id
        WHERE u.username LIKE ?
        ORDER BY timestamp DESC
    """
    
    # search_param uses double quotes for FTS5 exact matching
    search_param = f'"{clean_q}"'
    # like_param uses wildcards for partial username matching
    like_param = f'%{clean_q}%'
    
    try:
        msgs = db.execute(query, (search_param, like_param)).fetchall()
    except sqlite3.OperationalError:
        # Fallback if the FTS5 table is missing or corrupted
        fallback = """
            SELECT m.*, u.username, u.age 
            FROM messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.content LIKE ? OR u.username LIKE ?
            ORDER BY timestamp DESC
        """
        msgs = db.execute(fallback, (like_param, like_param)).fetchall()
    
    db.close()
    
    # 4. Return the response
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={
            "messages": msgs, 
            "user": request.cookies.get("username"),
            "search_query": q,
            "page": 1, 
            "has_next": False, 
            "has_prev": False
        }
    )

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