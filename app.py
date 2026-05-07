from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import uvicorn

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# -----------------------
# DATABASE CONNECTION
# -----------------------
def get_db_connection():
    conn = sqlite3.connect("database.db", check_same_thread=False)
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
            "text": row["content"],
            "timestamp": row["timestamp"],
            "username": row["username"],
            "age": row["age"]
        }
        for row in rows
    ]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "messages": messages_list,
            "user": request.cookies.get("username")
        }
    )


# -----------------------
# LOGIN PAGE (GET)
# -----------------------
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
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
        "create_user.html",
        {"request": request}
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
    return templates.TemplateResponse(
        "create_message.html",
        {"request": request}
    )


# -----------------------
# CREATE MESSAGE (POST)
# -----------------------
@app.post("/create_message")
async def create_message(request: Request, content: str = Form(...)):
    user_id = request.cookies.get("user_id")

    if user_id:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO messages (user_id, content) VALUES (?, ?)",
            (user_id, content)
        )
        conn.commit()
        conn.close()

    return RedirectResponse("/", status_code=303)


# -----------------------
# RUN SERVER
# -----------------------
if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
