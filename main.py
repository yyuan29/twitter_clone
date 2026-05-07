from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import uvicorn

app = FastAPI()

# Static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates folder
templates = Jinja2Templates(directory="templates")


# -----------------------
# DATABASE CONNECTION
# -----------------------
def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# -----------------------
# HOME PAGE
# -----------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = get_db_connection()

    query = """
        SELECT messages.content, messages.timestamp, users.username, users.age
        FROM messages
        JOIN users ON messages.user_id = users.id
        ORDER BY messages.timestamp DESC
    """

    rows = conn.execute(query).fetchall()
    conn.close()

    messages_list = [
        {
            "text": row["content"],
            "timestamp": row["timestamp"],
            "username": row["username"],
            "age": row["age"],
        }
        for row in rows
    ]

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "messages": messages_list
        }
    )


# -----------------------
# LOGIN PAGE (FIXED - WAS MISSING ROUTE DECORATOR)
# -----------------------
@app.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {"request": request}
    )


# -----------------------
# LOGOUT PAGE
# -----------------------
@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    return templates.TemplateResponse(
        "logout.html",
        {"request": request}
    )


# -----------------------
# CREATE MESSAGE PAGE
# -----------------------
@app.get("/create_message", response_class=HTMLResponse)
async def create_message(request: Request):
    return templates.TemplateResponse(
        "create_message.html",
        {"request": request}
    )


# -----------------------
# CREATE USER PAGE
# -----------------------
@app.get("/create_user", response_class=HTMLResponse)
async def create_user(request: Request):
    return templates.TemplateResponse(
        "create_user.html",
        {"request": request}
    )


# -----------------------
# RUN SERVER
# -----------------------
if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)