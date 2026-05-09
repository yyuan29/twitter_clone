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

LANGUAGES = {
    "en": {
        "home": "Home", "profile": "My Profile", "post": "New Post", "settings": "Settings", 
        "logout": "Logout", "login": "Login", "register": "Register", "search_placeholder": "Search chirps...",
        "feed_label": "Latest Feed", "reply": "Reply", "edit": "Edit", "delete": "Delete", "save": "Save"
    },
    "fr": {
        "home": "Accueil", "profile": "Mon Profil", "post": "Nouveau Post", "settings": "Paramètres", 
        "logout": "Déconnexion", "login": "Connexion", "register": "S'inscrire", "search_placeholder": "Chercher...",
        "feed_label": "Flux Récent", "reply": "Répondre", "edit": "Modifier", "delete": "Supprimer", "save": "Enregistrer"
    },
    "zh": {
        "home": "首页", "profile": "个人资料", "post": "发布动态", "settings": "设置", 
        "logout": "退出登录", "login": "登录", "register": "注册", "search_placeholder": "搜索动态...",
        "feed_label": "最新动态", "reply": "回复", "edit": "编辑", "delete": "删除", "save": "保存"
    }
}

# -----------------------
# APP SETUP
# -----------------------
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

# --- UTILS ---
def linkify(text):
    if not text: return ""
    text = html.escape(str(text))
    text = re.sub(r'(https?://[^\s]+|www\.[^\s]+)', 
                  lambda m: f'<a href="{"http://" if m.group(0).startswith("www") else ""}{m.group(0)}" target="_blank">{m.group(0)}</a>', 
                  text)
    text = re.sub(r'@(\w+)', 
                  r'<a href="/profile/\1" class="mention">@\1</a>', 
                  text)
    return text

templates.env.globals["linkify"] = linkify

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Users table
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        age INTEGER,
        bio TEXT
    )''')

    # FIX: Single messages table definition with ALL columns including parent_id
    conn.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        edited_at TEXT,
        parent_id INTEGER DEFAULT NULL
    )''')

    # Likes table
    conn.execute('''CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message_id INTEGER,
        UNIQUE(user_id, message_id)
    )''')

    # FTS5 search table
    conn.execute('CREATE VIRTUAL TABLE IF NOT EXISTS messages_search USING fts5(content, message_id UNINDEXED)')

    # Auto-fix: add bio column to old databases if missing
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'bio' not in columns:
        conn.execute('ALTER TABLE users ADD COLUMN bio TEXT')

    # Auto-fix: add parent_id column to old databases if missing
    cursor = conn.execute("PRAGMA table_info(messages)")
    msg_columns = [column[1] for column in cursor.fetchall()]
    if 'parent_id' not in msg_columns:
        conn.execute('ALTER TABLE messages ADD COLUMN parent_id INTEGER DEFAULT NULL')

    conn.commit()
    return conn

# -----------------------
# HOME FEED (WITH PAGINATION)
# -----------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, page: int = 1):
    if page < 1:
        page = 1

    limit = 50
    offset = (page - 1) * limit

    db = get_db()
    total_messages = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    query = f'''
        SELECT messages.*, users.username, users.age FROM messages
        LEFT JOIN users ON messages.user_id = users.id
        ORDER BY messages.timestamp DESC
        LIMIT {limit} OFFSET {offset}
    '''
    msgs = db.execute(query).fetchall()
    db.close()

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
# AUTH ROUTES
# -----------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
    db.close()
    if not user:
        return HTMLResponse("Invalid login. <a href='/login'>Try again</a>", 401)
    resp = RedirectResponse("/", 303)
    resp.set_cookie("username", username)
    resp.set_cookie("user_id", str(user["id"]))
    return resp

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={"request": request})

@app.post("/register")
async def register_user(username: str = Form(...), password: str = Form(...), confirm_password: str = Form(...), age: int = Form(...)):
    if password != confirm_password:
        return HTMLResponse("Passwords mismatch", 400)
    db = get_db()
    try:
        cursor = db.execute("INSERT INTO users (username, password, age, bio) VALUES (?, ?, ?, ?)", (username, password, age, ""))
        db.commit()
        resp = RedirectResponse("/", 303)
        resp.set_cookie("username", username)
        resp.set_cookie("user_id", str(cursor.lastrowid))
        return resp
    except sqlite3.IntegrityError:
        return HTMLResponse("Username taken!", 400)
    finally:
        db.close()

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
    return templates.TemplateResponse(request=request, name="reset_password.html", context={"request": request})

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

    if new_password != confirm_password:
        return templates.TemplateResponse(request=request, name="reset_password.html",
                                          context={"request": request, "error": "New passwords do not match!"})

    db = get_db()
    user_record = db.execute("SELECT password FROM users WHERE username = ?", (username,)).fetchone()

    if not user_record or not pbkdf2_sha256.verify(old_password, user_record["password"]):
        db.close()
        return templates.TemplateResponse(request=request, name="reset_password.html",
                                          context={"request": request, "error": "Current password is incorrect."})

    new_hashed = pbkdf2_sha256.hash(new_password)
    db.execute("UPDATE users SET password = ? WHERE username = ?", (new_hashed, username))
    db.commit()
    db.close()
    return RedirectResponse(f"/profile/{username}", 303)

# -----------------------
# PROFILE & BIO ROUTES
# -----------------------
@app.get("/profile/{username}", response_class=HTMLResponse)
async def view_profile(request: Request, username: str):
    db = get_db()
    user_data = db.execute("SELECT * FROM users WHERE username LIKE ?", (username,)).fetchone()

    if not user_data:
        db.close()
        return HTMLResponse(f"User '{username}' not found", 404)

    msgs = db.execute("SELECT * FROM messages WHERE user_id = ? ORDER BY timestamp DESC", (user_data['id'],)).fetchall()
    db.close()

    logged_in_user = request.cookies.get("username")
    is_own_profile = logged_in_user and logged_in_user.lower() == user_data['username'].lower()

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
    username = request.cookies.get("username")
    if not username or username == "None":
        return RedirectResponse("/login", 303)
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
    if not request.cookies.get("user_id"):
        return RedirectResponse("/login", 303)
    return templates.TemplateResponse(request=request, name="create_message.html", context={"request": request})

# FIX 1: Changed @app.get to @app.post
# FIX 2: Removed duplicate INSERT INTO messages
@app.post("/create_message")
async def create_message(request: Request, content: str = Form(...)):
    u_id = request.cookies.get("user_id")
    if not u_id:
        return RedirectResponse("/login", 303)
    db = get_db()

    # Insert into main messages table (only once!)
    cursor = db.execute("INSERT INTO messages (user_id, content) VALUES (?, ?)", (int(u_id), content))
    msg_id = cursor.lastrowid

    # Insert into FTS5 search table
    db.execute("INSERT INTO messages_search (content, message_id) VALUES (?, ?)", (content, msg_id))

    db.commit()
    db.close()
    return RedirectResponse("/", 303)

@app.get("/search", response_class=HTMLResponse)
async def search_messages(request: Request, q: str = ""):
    db = get_db()
    clean_q = q.replace("@", "").strip()

    if not clean_q:
        db.close()
        return RedirectResponse("/", 303)

    count_search = db.execute("SELECT COUNT(*) FROM messages_search").fetchone()[0]
    if count_search == 0:
        db.execute("INSERT INTO messages_search(content, message_id) SELECT content, id FROM messages")
        db.commit()

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
    search_param = f'"{clean_q}"'
    like_param = f'%{clean_q}%'

    try:
        msgs = db.execute(query, (search_param, like_param)).fetchall()
    except sqlite3.OperationalError:
        fallback = """
            SELECT m.*, u.username, u.age 
            FROM messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.content LIKE ? OR u.username LIKE ?
            ORDER BY timestamp DESC
        """
        msgs = db.execute(fallback, (like_param, like_param)).fetchall()

    db.close()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
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
    if not u_id:
        return RedirectResponse("/login", 303)
    db = get_db()
    db.execute("DELETE FROM messages WHERE id=? AND user_id=?", (msg_id, int(u_id)))
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

# --- EDIT MESSAGE ---
@app.get("/edit_message/{msg_id}")
async def edit_message_page(request: Request, msg_id: int):
    u_id = request.cookies.get("user_id")
    if not u_id: 
        print("DEBUG: No user_id cookie found. Redirecting to login.")
        return RedirectResponse("/login", 303)
    
    db = get_db()
    # Let's look for the message without the user check first to see if it exists
    msg = db.execute("SELECT * FROM messages WHERE id=?", (msg_id,)).fetchone()
    db.close()
    
    if not msg:
        print(f"DEBUG: Message ID {msg_id} does not exist in database.")
        return HTMLResponse("Message Not Found", 404)
    
    if int(msg['user_id']) != int(u_id):
        print(f"DEBUG: User {u_id} tried to edit User {msg['user_id']}'s message.")
        return HTMLResponse("Unauthorized: You do not own this message.", 403)
    
    return templates.TemplateResponse(
        request=request,
        name="edit_message.html", 
        context={
        "request": request,
        "message": msg,
        "user": request.cookies.get("username"),
        "t": get_translations(request)
    })
@app.post("/edit_message/{msg_id}")
async def edit_message_submit(msg_id: int, request: Request, content: str = Form(...)):
    u_id = request.cookies.get("user_id")
    if not u_id: return RedirectResponse("/login", 303)
    
    db = get_db()
    # Update the content AND record the current time as the edit time
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE messages SET content=?, edited_at=? WHERE id=? AND user_id=?", 
        (content, now, msg_id, int(u_id))
    )
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

# --- REPLY ---
@app.post("/reply/{parent_id}")
async def post_reply(request: Request, parent_id: int, content: str = Form(...)):
    u_id = request.cookies.get("user_id")
    if not u_id:
        return RedirectResponse("/login", 303)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO messages (user_id, content, parent_id) VALUES (?, ?, ?)",
        (int(u_id), content, parent_id)
    )
    msg_id = cursor.lastrowid
    db.execute("INSERT INTO messages_search (content, message_id) VALUES (?, ?)", (content, msg_id))
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

# --- TRANSLATIONS ---
def get_translations(request: Request):
    lang_code = request.cookies.get("language", "en")
    return LANGUAGES.get(lang_code, LANGUAGES["en"])

templates.env.globals["get_t"] = get_translations

@app.get("/set_lang/{lang}")
async def set_language(lang: str):
    response = RedirectResponse(url="/", status_code=303)
    if lang in LANGUAGES:
        response.set_cookie(key="language", value=lang, max_age=2592000)
    return response

@app.get("/api/messages")
async def get_messages_json():
    db = get_db()
    # Fetch all messages from the database
    rows = db.execute("""
        SELECT m.id, m.content, m.timestamp, m.edited_at, u.username 
        FROM messages m 
        JOIN users u ON m.user_id = u.id 
        ORDER BY m.timestamp DESC
    """).fetchall()
    db.close()

    # Convert the SQLite rows into a list of dictionaries
    messages_list = []
    for row in rows:
        messages_list.append({
            "id": row["id"],
            "username": row["username"],
            "content": row["content"],
            "timestamp": row["timestamp"],
            "edited_at": row["edited_at"]
        })

    return {"messages": messages_list}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)