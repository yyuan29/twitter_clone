from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from passlib.hash import pbkdf2_sha256
from itsdangerous import URLSafeTimedSerializer
from fastapi.responses import JSONResponse

import sqlite3
import os
import re
import html
import markdown
from datetime import datetime
import bleach
import random
DB_PATH = "database.db"



# -----------------------
# APP SETUP
# -----------------------
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

SECRET_KEY = "your-super-secret-key-12345"
serializer = URLSafeTimedSerializer(SECRET_KEY)

def get_current_user_id(request: Request):
    signed_user = request.cookies.get("user_id")

    if not signed_user:
        return None

    try:
        user_id = serializer.loads(signed_user, max_age=604800)
        return int(user_id)

    except Exception:
        return None

# -----------------------
# JSON API
# ----------------------- 
@app.get("/api/messages")
async def api_messages(page: int = 1):
    if page < 1:
        page = 1

    limit = 50
    offset = (page - 1) * limit

    db = get_db()

    rows = db.execute("""
        SELECT m.id, m.content, m.timestamp, m.edited_at,
               u.username
        FROM messages m
        LEFT JOIN users u ON m.user_id = u.id
        ORDER BY m.timestamp DESC
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()

    db.close()

    messages = []
    for r in rows:
        messages.append({
            "id": r["id"],
            "username": r["username"],
            "content": r["content"],
            "timestamp": r["timestamp"],
            "edited_at": r["edited_at"]
        })

    return JSONResponse(content={
        "page": page,
        "messages": messages
    })

# -----------------------
# MULTI-LANGUAGE SUPPORT
# -----------------------
LANGUAGES = {
    "en": {
        "home": "Home",
        "profile": "My Profile",
        "post": "New Post",
        "settings": "Settings",
        "logout": "Logout",
        "login": "Login",
        "register": "Register",
        "search_placeholder": "Search messages...",
        "feed_label": "Latest Feed",
        "reply": "Reply",
        "edit": "Edit",
        "delete": "Delete",
        "save": "Save",
        "create_account": "Create Account",
        "username": "Username",
        "password": "Password",
        "confirm_password": "Confirm Password",
        "age": "Age",
        "submit": "Submit",
        "message_placeholder": "What's happening?"
    },

    "fr": {
        "home": "Accueil",
        "profile": "Mon Profil",
        "post": "Nouveau Message",
        "settings": "Paramètres",
        "logout": "Déconnexion",
        "login": "Connexion",
        "register": "S'inscrire",
        "search_placeholder": "Rechercher des messages...",
        "feed_label": "Fil d’actualité",
        "reply": "Répondre",
        "edit": "Modifier",
        "delete": "Supprimer",
        "save": "Enregistrer",
        "create_account": "Créer un compte",
        "username": "Nom d'utilisateur",
        "password": "Mot de passe",
        "confirm_password": "Confirmer le mot de passe",
        "age": "Âge",
        "submit": "Valider",
        "message_placeholder": "Quoi de neuf ?"
    },

    "zh": {
        "home": "首页",
        "profile": "个人资料",
        "post": "发布动态",
        "settings": "设置",
        "logout": "退出登录",
        "login": "登录",
        "register": "注册",
        "search_placeholder": "搜索消息...",
        "feed_label": "最新动态",
        "reply": "回复",
        "edit": "编辑",
        "delete": "删除",
        "save": "保存",
        "create_account": "创建账户",
        "username": "用户名",
        "password": "密码",
        "confirm_password": "确认密码",
        "age": "年龄",
        "submit": "提交",
        "message_placeholder": "你在想什么？"
    }
}

def get_translations(request: Request):
    lang = request.cookies.get("language", "en")
    return LANGUAGES.get(lang, LANGUAGES["en"])

@app.get("/set_lang/{lang}")
async def set_language(lang: str):
    response = RedirectResponse(url="/", status_code=303)
    if lang in LANGUAGES:
        # We use a long max_age so the choice is remembered
        response.set_cookie(key="language", value=lang, max_age=2592000)
    return response

# This allows you to just type {{ t.home }} in ANY template 
# as long as you pass the request in the context.
@app.middleware("http")
async def add_translations_to_request(request: Request, call_next):
    request.state.t = get_translations(request)
    response = await call_next(request)
    return response

# Update your globals to use the state
templates.env.globals["get_t"] = get_translations
# -----------------------
# DATABASE CONNECTION
# Creates a safe SQLite connection
# -----------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            age INTEGER,
            bio TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            edited_at TEXT,
            parent_id INTEGER DEFAULT NULL
        )
    """)

    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_search
        USING fts5(content, message_id UNINDEXED)
    """)

    conn.commit()
    return conn

def db_execute(query, params=()):
    """
    Safe wrapper so you NEVER accidentally concat SQL strings.
    """
    db = get_db()
    cur = db.execute(query, params)
    db.commit()
    db.close()
    return cur

def ensure_bio_column():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # check existing columns
    cur.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cur.fetchall()]

    # only add if missing
    if "bio" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN bio TEXT")
        conn.commit()
    conn.close()

DEFAULT_BIOS = [
    "Just vibing on BirdieMessages 🐦",
    "CS student grinding assignments 💻",
    "Professional procrastinator",
    "Surviving college one bug at a time",
    "Debugging my life like my code",
    "Coffee enthusiast ☕",
    "Learning and building things",
    "Here for the memes"
]

def backfill_bios():
    db = get_db()

    users = db.execute("SELECT id, username, bio FROM users").fetchall()
    PROTECTED_USERS = ["yuan29", "YumoY"]

    for u in users:
        # skip your own account
        if u["username"] in PROTECTED_USERS:
            continue

       # only fill missing bios
        if u["bio"] is None or u["bio"].strip() == "":
            bio = random.choice(DEFAULT_BIOS)

            db.execute(
                "UPDATE users SET bio = ? WHERE id = ?",
                (bio, u["id"])
            )

    db.commit()
    db.close()

ensure_bio_column()
backfill_bios()

# -----------------------
# SECURITY HELPER
# -----------------------
def linkify(text):
    if not text:
        return ""

    # Convert markdown safely
    html_content = markdown.markdown(
        text,
        extensions=["extra", "nl2br"]
    )

    allowed_tags = [
        'h1', 'h2', 'h3',
        'p', 'br',
        'strong', 'em',
        'ul', 'ol', 'li',
        'a', 'code', 'pre'
    ]

    allowed_attrs = {
        'a': ['href', 'title', 'target', 'rel']
    }

    # FIRST SANITIZE
    clean_html = bleach.clean(
        html_content,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=['http', 'https'],
        strip=True
    )

    # Convert URLs into links
    clean_html = re.sub(
        r'(https?://[^\s<]+)',
        r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>',
        clean_html
    )

    # Convert mentions safely
    clean_html = re.sub(
        r'@(\w+)',
        r'<a href="/profile/\1">@\1</a>',
        clean_html
    )

    # SANITIZE AGAIN AFTER REGEX
    clean_html = bleach.clean(
        clean_html,
        tags=allowed_tags,
        attributes=allowed_attrs,
        protocols=['http', 'https'],
        strip=True
    )

    return clean_html
templates.env.globals.update(linkify=linkify)

# -----------------------
# HOME PAGE (FEED)
# Shows all top-level posts safely with pagination
# -----------------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, page: int = 1):
    if page < 1: page = 1
    limit = 50
    offset = (page - 1) * limit

    db = get_db()
    # The SQL is perfect, but ensure your database has 'username' in the users table
    rows = db.execute("""
    WITH RECURSIVE message_tree AS (
        SELECT id, id as root_id, timestamp, 0 as depth
        FROM messages
        WHERE parent_id IS NULL

        UNION ALL

        SELECT m.id, mt.root_id, m.timestamp, mt.depth + 1
        FROM messages m
        JOIN message_tree mt ON m.parent_id = mt.id
    )
    SELECT m.*, u.username, mt.depth, mt.root_id
    FROM messages m
    JOIN message_tree mt ON m.id = mt.id
    LEFT JOIN users u ON m.user_id = u.id
    ORDER BY mt.root_id DESC, m.id ASC
    LIMIT ? OFFSET ?
""", (limit, offset)).fetchall()

    total_row = db.execute("SELECT COUNT(*) FROM messages").fetchone()
    total = total_row[0] if total_row else 0
    db.close()
    
    # Get the logged-in user from the cookie
    logged_in_user = request.cookies.get("username")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "messages": rows,
            "page": page,
            "has_next": (offset + limit) < total,
            "has_prev": page > 1,
            "user": logged_in_user,
            "t": get_translations(request)
        }
    )

# -----------------------
# LOGIN (SECURE PASSWORD CHECK)
# -----------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context=
        {"request": request,
          "t": get_translations(request)
        }
    )

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    db = get_db()

    user = db.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    db.close()

    if not user or not pbkdf2_sha256.verify(password, user["password"]):
        return HTMLResponse("Invalid login", status_code=401)

    response = RedirectResponse("/", status_code=303)

    signed_user_id = serializer.dumps(user["id"])

    response.set_cookie(
        "user_id",
        signed_user_id,
        httponly=True,
        samesite="lax",
        secure=False
    )

    response.set_cookie(
        "username",
        user["username"],
        httponly=False,
        samesite="lax"
    )

    return response

# -----------------------
# REGISTER (HASH PASSWORD)
# -----------------------
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """
    Renders the user registration page.
    Only displays the HTML form.
    """
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "request": request,
            "t": get_translations(request)
        }
    )

@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    age: int = Form(...)
):

    username = username.strip()

    # Username validation
    if not re.match(r'^[A-Za-z0-9_]{3,20}$', username):
        return HTMLResponse(
            "Username must be 3-20 characters and only contain letters, numbers, and underscores.",
            400
        )

    if password != confirm_password:
        return HTMLResponse("Passwords do not match", 400)

    hashed = pbkdf2_sha256.hash(password)

    db = get_db()

    try:
        cur = db.execute(
            """
            INSERT INTO users (
                username,
                password,
                age
            )
            VALUES (?, ?, ?)
            """,
            (username, hashed, age)
        )

        db.commit()

        user_id = cur.lastrowid

    except sqlite3.IntegrityError:
        db.close()
        return HTMLResponse("Username already exists", 400)

    db.close()

    signed_user_id = serializer.dumps(user_id)

    response = RedirectResponse("/", status_code=303)

    response.set_cookie(
        "user_id",
        signed_user_id,
        httponly=True,
        samesite="lax",
        secure=False
    )

    response.set_cookie(
        "username",
        username,
        httponly=False,
        samesite="lax"
    )

    return response
# -----------------------
# Password Reset
# -----------------------
@app.get("/change_password", response_class=HTMLResponse)
async def change_password_page(request: Request):
    return HTMLResponse("""
    <form method="post">
        <input type="password" name="old_password" placeholder="Old password" required><br>
        <input type="password" name="new_password" placeholder="New password" required><br>
        <input type="password" name="confirm_password" placeholder="Confirm password" required><br>
        <button type="submit">Change Password</button>
    </form>
    """)

@app.post("/change_password")
async def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...)
):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse("/login", 303)

    if new_password != confirm_password:
        return HTMLResponse("Passwords do not match", 400)

    db = get_db()

    user = db.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user or not pbkdf2_sha256.verify(old_password, user["password"]):
        db.close()
        return HTMLResponse("Incorrect old password", 400)

    new_hashed = pbkdf2_sha256.hash(new_password)

    db.execute(
        "UPDATE users SET password = ? WHERE id = ?",
        (new_hashed, user_id)
    )

    db.commit()
    db.close()

    return RedirectResponse("/", 303)

# -----------------------
# Profiles
# -----------------------
@app.get("/profile/{username}", response_class=HTMLResponse)
async def view_profile(request: Request, username: str):
    db = get_db()

    user = db.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if not user:
        db.close()
        return HTMLResponse("User not found", 404)

    messages = db.execute(
        """
        SELECT m.*, u.username
        FROM messages m
        JOIN users u ON m.user_id = u.id
        WHERE m.user_id = ?
        ORDER BY m.timestamp DESC
        """,
        (user["id"],)
    ).fetchall()

    db.close()

    current_user = request.cookies.get("username")

    return templates.TemplateResponse(
        request,
        "profile.html",
        {
            "request": request,
            "profile_user": user,
            "messages": messages,
            "user": current_user,
            "is_own_profile": current_user == user["username"],
            "t": get_translations(request)
        }
    )
@app.post("/update_profile")
async def update_profile(request: Request, bio: str = Form(...)):
    user_id = get_current_user_id(request)

    if not user_id:
        return RedirectResponse("/login", 303)

    bio = bio.strip()

    if len(bio) > 300:
        return HTMLResponse("Bio too long", 400)

    db = get_db()

    db.execute(
        "UPDATE users SET bio = ? WHERE id = ?",
        (bio, user_id)
    )

    db.commit()
    db.close()

    username = request.cookies.get("username")

    return RedirectResponse(f"/profile/{username}", 303)
# -----------------------
# Creating Messages
# -----------------------
@app.get("/create_message", response_class=HTMLResponse)
async def create_message_page(request: Request):
    if not request.cookies.get("user_id"):
        return RedirectResponse("/login", 303)

    return templates.TemplateResponse(
        request=request,
        name="create_message.html",
        context=
        {
            "request": request,
            "user": request.cookies.get("username"),
            "t": get_translations(request)
        }
    )
@app.post("/create_message")
async def create_message(
    request: Request,
    content: str = Form(...)
):

    user_id = get_current_user_id(request)

    if not user_id:
        return RedirectResponse("/login", 303)

    content = content.strip()

    if not content:
        return HTMLResponse("Message cannot be empty", 400)

    if len(content) > 5000:
        return HTMLResponse("Message too long", 400)

    db = get_db()

    cursor = db.execute(
        "INSERT INTO messages (user_id, content) VALUES (?, ?)",
        (user_id, content)
    )

    msg_id = cursor.lastrowid

    db.execute(
        "INSERT INTO messages_search (content, message_id) VALUES (?, ?)",
        (content, msg_id)
    )

    db.commit()
    db.close()

    return RedirectResponse("/", 303)
# -----------------------
# Deleting Messages
# -----------------------
@app.get("/delete_message/{msg_id}")
async def delete_message(request: Request, msg_id: int):

    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse("/login", 303)

    db = get_db()

    db.execute(
    "DELETE FROM messages_search WHERE message_id = ?",
    (msg_id,)
    
    )
    db.execute(
        "DELETE FROM messages WHERE id = ? AND user_id = ?",
        (msg_id, user_id)
    )

    db.commit()
    db.close()

    return RedirectResponse("/", 303)


# -----------------------
# Editting Messages
# -----------------------
@app.get("/edit_message/{msg_id}", response_class=HTMLResponse)
async def edit_message_page(request: Request, msg_id: int):
    user_id = request.cookies.get("user_id")

    # must be logged in
    if not user_id:
        return RedirectResponse("/login", 303)

    db = get_db()

    # fetch the message safely
    msg = db.execute(
        "SELECT * FROM messages WHERE id = ? AND user_id = ?",
        (msg_id, int(user_id))
    ).fetchone()

    db.close()

    if not msg:
        return HTMLResponse("Message not found or unauthorized", status_code=403)

    return templates.TemplateResponse(
        request=request,
        name="edit_message.html",
        context=
        {
            "request": request,
            "message": msg,
            "user": request.cookies.get("username"),
            "t": get_translations(request)
        }
    )
@app.post("/edit_message/{msg_id}")
async def edit_message(
    msg_id: int,
    request: Request,
    content: str = Form(...)
):

    user_id = get_current_user_id(request)

    if not user_id:
        return RedirectResponse("/login", 303)

    content = content.strip()

    if not content:
        return HTMLResponse("Message cannot be empty", 400)

    if len(content) > 5000:
        return HTMLResponse("Message too long", 400)

    db = get_db()

    db.execute("""
        UPDATE messages
        SET content = ?, edited_at = ?
        WHERE id = ? AND user_id = ?
    """, (
        content,
        datetime.now(),
        msg_id,
        user_id
    ))

    db.execute(
        "DELETE FROM messages_search WHERE message_id = ?",
        (msg_id,)
    )

    db.execute(
        "INSERT INTO messages_search (content, message_id) VALUES (?, ?)",
        (content, msg_id)
    )

    db.commit()
    db.close()

    return RedirectResponse("/", 303)

# -----------------------
# Search
# -----------------------
@app.get("/search", response_class=HTMLResponse)
async def search(request: Request, q: str = ""):
    if not q.strip():
        return RedirectResponse("/", 303)

    db = get_db()

    # Ensure FTS5 table is populated if this is the first time running
    count = db.execute("SELECT COUNT(*) FROM messages_search").fetchone()[0]
    if count == 0:
        db.execute("INSERT INTO messages_search(content, message_id) SELECT content, id FROM messages")
        db.commit()

    clean_q = re.sub(r'[^a-zA-Z0-9\s]', '', q).strip()

    if not clean_q:
        db.close()
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "messages": [],
                "user": request.cookies.get("username"),
                "page": 1,
                "has_next": False,
                "has_prev": False,
                "t": get_translations(request)
            }
        )

    fts_query = f'"{clean_q}"'

    try:
        rows = db.execute("""
            SELECT m.*, u.username
            FROM messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.id IN (
                SELECT message_id
                FROM messages_search
                WHERE messages_search MATCH ?
            )
            ORDER BY m.timestamp DESC
        """, (fts_query,)).fetchall()
    except sqlite3.OperationalError:
        rows = db.execute("""
            SELECT m.*, u.username
            FROM messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.content LIKE ?
            ORDER BY m.timestamp DESC
        """, (f"%{clean_q}%",)).fetchall()
    finally:
        db.close()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "messages": rows,
            "user": request.cookies.get("username"),
            "page": 1,
            "has_next": False,
            "has_prev": False,
            "t": get_translations(request)
        }
    )
# -----------------------
# Reply
# -----------------------
@app.get("/message/{msg_id}", response_class=HTMLResponse)
async def view_message(request: Request, msg_id: int):
    db = get_db()
    
    # 1. Get the main message
    main_msg = db.execute("""
        SELECT m.*, u.username 
        FROM messages m 
        LEFT JOIN users u ON m.user_id = u.id 
        WHERE m.id = ?
    """, (msg_id,)).fetchone()

    if not main_msg:
        db.close()
        return HTMLResponse(content="Message not found", status_code=404)

    # 2. Get the replies (where parent_id matches this msg_id)
    replies = db.execute("""
        SELECT m.*, u.username 
        FROM messages m 
        LEFT JOIN users u ON m.user_id = u.id 
        WHERE m.parent_id = ?
        ORDER BY m.timestamp ASC
    """, (msg_id,)).fetchall()
    
    db.close()

    return templates.TemplateResponse(
        request=request,
        name="reply_message.html", 
        context=
        {
            "request": request, 
            "message": main_msg, 
            "replies": replies,
            "user": request.cookies.get("username"),
            "t": get_translations(request)
        }
    )
@app.post("/post_reply/{parent_id}")
async def post_reply(
    request: Request,
    parent_id: int,
    content: str = Form(...)
):
    user_id = get_current_user_id(request)

    if not user_id:
        return RedirectResponse("/login", status_code=303)

    content = content.strip()

    if not content:
        return HTMLResponse("Message cannot be empty", 400)

    if len(content) > 5000:
        return HTMLResponse("Message too long", 400)

    db = get_db()

    # Verify parent exists
    parent_exists = db.execute(
        "SELECT id FROM messages WHERE id = ?",
        (parent_id,)
    ).fetchone()

    if not parent_exists:
        db.close()
        return HTMLResponse("Parent message not found", 404)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        db.execute("""
            INSERT INTO messages (
                user_id,
                content,
                timestamp,
                parent_id
            )
            VALUES (?, ?, ?, ?)
        """, (user_id, content, now, parent_id))

        db.commit()

    except Exception as e:
        db.close()
        return HTMLResponse(f"Database error: {e}", 500)

    db.close()

    return RedirectResponse(
        f"/message/{parent_id}",
        status_code=303
    )

# -----------------------
# Logout
# -----------------------
@app.get("/logout")
async def logout():

    response = RedirectResponse("/", 303)

    response.delete_cookie("username")
    response.delete_cookie("user_id")

    return response

# -----------------------
# Delete Account
# -----------------------
@app.get("/delete_account", response_class=HTMLResponse)
async def delete_account_confirm(request: Request):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse("/login", 303)

    return HTMLResponse("""
    <html>
        <body style="font-family: Arial; text-align:center; margin-top:100px;">
            <h2 style="color:red;">⚠️ Delete Account</h2>
            <p>This action is permanent. All your messages will be deleted.</p>

            <form method="post" action="/delete_account">
                <button style="background:red; color:white; padding:10px 20px; border:none; border-radius:8px;">
                    Yes, delete my account
                </button>
            </form>

            <br>
            <a href="/" style="color:gray;">Cancel</a>
        </body>
    </html>
    """)

@app.post("/delete_account")
async def delete_account(request: Request):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse("/login", 303)

    db = get_db()

    db.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))

    db.commit()
    db.close()

    response = RedirectResponse("/register", 303)
    response.delete_cookie("user_id")
    response.delete_cookie("username")

    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)