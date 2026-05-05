from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import uvicorn

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

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

    messages_list = []
    for row in rows:
        messages_list.append({
            'text': row['content'],
            'timestamp': row['timestamp'],
            'username': row['username'],
            'age': row['age']
        })

    # FastAPI requires passing 'request' into the template
    return templates.TemplateResponse(
    request=request, 
    name="index.html", 
    context={"messages": messages_list}
    )

async def login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    return templates.TemplateResponse("logout.html", {"request": request})

@app.get("/create_message", response_class=HTMLResponse)
async def create_message(request: Request):
    return templates.TemplateResponse("create_message.html", {"request": request})

@app.get("/create_user", response_class=HTMLResponse)
async def create_user(request: Request):
    return templates.TemplateResponse("create_user.html", {"request": request})

if __name__ == "__main__":
    # This tells Python to start the server when you run the file
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
