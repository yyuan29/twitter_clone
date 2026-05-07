from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import uvicorn
import os
from datetime import datetime

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def linkify(text):
    if text is None: return ""
    import re
    return re.sub(r'(https?://[^\s]+)', r'<a href="\1" target="_blank">\1</a>', str(text))
templates.env.globals.update(linkify=linkify)

# -----------------------
# DATABASE CONNECTION
# -----------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------
# HOME PAGE
# -----------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = get_db_connection()

    query = """
        SELECT m.content, m.timestamp, u.username, u.age
        FROM messages m
        JOIN users u ON m.user_id = u.id
        ORDER BY m.timestamp DESC
    """

    rows = conn.execute(query).fetchall()
    conn.close()

    # FIXED: consistent + Jinja-safe format
    messages_list = [
        {
             "id": row["id"],
            "content": row["content"],
            "timestamp": row["timestamp"],
            "username": row["username"],
            "age": row["age"],
            "user_id": row["user_id"]
        }
        for row in rows
    ]

    return templates.TemplateResponse(
    request=request, 
    name="index.html", 
    context={"messages": messages_list, "user": request.cookies.get("username")}
)

# -----------------------
# LOGIN PAGE (GET)
# -----------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={
            "user": request.cookies.get("username")
        }
    )


# -----------------------
# LOGIN HANDLER (POST)
# -----------------------
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password)
    ).fetchone()

    conn.close()

    if not user:
        return HTMLResponse("Invalid login", status_code=401)

    response = RedirectResponse("/", status_code=303)
    response.set_cookie("username", username)
    response.set_cookie("user_id", str(user["id"]))
    return response


# -----------------------
# LOGOUT
# -----------------------
@app.get("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("username")
    response.delete_cookie("user_id")
    return response


# -----------------------
# CREATE USER (GET)
# -----------------------
@app.get("/create_user", response_class=HTMLResponse)
async def create_user_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="create_user.html", 
        context={}
    )


# -----------------------
# CREATE USER (POST)
# -----------------------
@app.post("/create_user")
async def create_user(
    username: str = Form(...),
    password: str = Form(...),
    p2: str = Form(...),
    age: int = Form(...)
):
    if password != p2:
        return HTMLResponse("Passwords don't match", status_code=400)

    conn = get_db_connection()

    try:
        conn.execute(
            "INSERT INTO users (username, password, age) VALUES (?, ?, ?)",
            (username, password, age)
        )
        conn.commit()
    except:
        conn.close()
        return HTMLResponse("User already exists", status_code=400)

    conn.close()
    return RedirectResponse("/login", status_code=303)


# -----------------------
# CREATE MESSAGE (GET)
# -----------------------
@app.get("/create_message", response_class=HTMLResponse)
async def create_message_page(request: Request):
    # Check if user is logged in (Requirement: Post link only for logged in users)
    if not request.cookies.get("username"):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request=request, 
        name="create_message.html", 
        context={
            "user": request.cookies.get("username")
        }
    )

# -----------------------
# CREATE MESSAGE 
# -----------------------
@app.post("/create_message")
async def handle_post_message(request: Request, content: str = Form(...)):
    # 1. Get the user_id from the cookie
    user_id = request.cookies.get("user_id")

    if not user_id:
        # If they aren't logged in, they shouldn't be posting
        return RedirectResponse(url="/login", status_code=303)

    # 2. Database transaction
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO messages (user_id, content) VALUES (?, ?)",
            (user_id, content)
        )
        conn.commit()
    except Exception as e:
        print(f"Error saving message: {e}")
    finally:
        conn.close()

    # 3. Redirect back to home
    return RedirectResponse(url="/", status_code=303)

# -----------------------
# DELETE MESSAGE 
# -----------------------
@app.get("/delete_message/{msg_id}")
async def delete_message(request: Request, msg_id: int):
    user_id = request.cookies.get("user_id")
    if not user_id: return RedirectResponse("/login", 303)
    
    db = get_db_connection()
    # Security: Only let the user delete their own messages
    db.execute("DELETE FROM messages WHERE id = ? AND user_id = ?", (msg_id, user_id))
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

# -----------------------
# EDIT MESSAGE 
# -----------------------
@app.get("/edit_message/{msg_id}", response_class=HTMLResponse)
async def edit_page(request: Request, msg_id: int):
    db = get_db_connection()
    msg = db.execute("SELECT * FROM messages WHERE id = ?", (msg_id,)).fetchone()
    db.close()
    return templates.TemplateResponse(request=request, name="edit_message.html", context={"message": msg})

@app.post("/edit_message/{msg_id}")
async def handle_edit(request: Request, msg_id: int, content: str = Form(...)):
    user_id = request.cookies.get("user_id")
    db = get_db_connection()
    # Update content and set the 'edited_at' timestamp
    db.execute("""
        UPDATE messages 
        SET content = ?, edited_at = ? 
        WHERE id = ? AND user_id = ?
    """, (content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg_id, user_id))
    db.commit()
    db.close()
    return RedirectResponse("/", 303)

    # Convert to standard dictionaries so Jinja2 can read them easily
    messages_list = [dict(row) for row in rows]

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "messages": messages_list, 
            "user": request.cookies.get("username")
        }
    )

# -----------------------
# RUN SERVER
# -----------------------
if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
