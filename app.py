from fastapi import FastAPI, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import uvicorn
import os

app = FastAPI()

# Requirement 3: Static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DB_PATH = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = get_db_connection()
    query = '''
        SELECT messages.content, messages.timestamp, users.username, users.age
        FROM messages
        JOIN users ON messages.user_id = users.id
        ORDER BY messages.timestamp DESC
    '''
    rows = conn.execute(query).fetchall()
    conn.close()
    
    # Requirement 2: List of dictionaries
    messages_list = [dict(row) for row in rows]

    return templates.TemplateResponse(
    request,
    "index.html",
    {
        "request": request,
        "messages": messages_list,
        "user": request.cookies.get("username")
    }
)

# --- LOG IN ---
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.cookies.get("username"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
    request,
    "login.html",
    {"request": request}
)

@app.post("/login")
async def login_action(username: str = Form(...), password: str = Form(...)):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password)).fetchone()
    conn.close()
    
    if user:
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(key="username", value=user["username"])
        response.set_cookie(key="user_id", value=str(user["id"]))
        return response
    else:
        # Simple error message
        return "Invalid username or password. Please go back."

# --- LOG OUT ---
@app.get("/logout")
async def logout(request: Request):
    # Requirement: Delete the cookies
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("username")
    response.delete_cookie("user_id")
    return response

# --- CREATE USER ---
@app.get("/create_user", response_class=HTMLResponse)
async def create_user_page(request: Request):
    return templates.TemplateResponse("create_user.html", {"request": request})

@app.post("/create_user")
async def create_user_action(username: str = Form(...), password: str = Form(...), password_confirm: str = Form(...), age: int = Form(...)):
    if password != password_confirm:
        return "Passwords do not match. Please go back."
    
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO users (username, password, age) VALUES (?, ?, ?)", (username, password, age))
        conn.commit()
    except sqlite3.IntegrityError:
        return "Error: Username already exists."
    finally:
        conn.close()
    
    return RedirectResponse("/login", status_code=303)

# --- CREATE MESSAGE ---
@app.get("/create_message", response_class=HTMLResponse)
async def create_message_page(request: Request):
    if not request.cookies.get("username"):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("create_message.html", {"request": request})

@app.post("/create_message")
async def create_message_action(request: Request, content: str = Form(...)):
    user_id = request.cookies.get("user_id")
    if user_id:
        conn = get_db_connection()
        conn.execute("INSERT INTO messages (user_id, content) VALUES (?, ?)", (user_id, content))
        conn.commit()
        conn.close()
    return RedirectResponse("/", status_code=303)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
