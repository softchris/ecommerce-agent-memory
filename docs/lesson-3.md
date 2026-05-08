# 📘 Lesson 3 — Adding a Web UI with FastAPI

## 👋 Welcome to the Final Build
You already have a local agent with SQL-backed memory.
Now you'll turn it into a small full-stack commerce app with a browser UI, saved users, and simple recommendations.

---
## 🎯 What You'll Learn
- Extend the database with users and sessions
- Keep per-user chat history
- Build a tiny product catalog
- Create a FastAPI backend
- Warm up Ollama on startup
- Serve a browser UI
- Score recommendations from conversation history

---
## 🧰 Prerequisites
Install the web packages:
```bash
uv add fastapi uvicorn[standard] httpx
```
Quick checks:
```bash
uv run python -c "import fastapi, httpx; print('ok')"
docker ps
ollama list
```
Make sure SQL Server and Ollama are both running.

---
## 👥 Step 1 — Add Users and Sessions
Replace `db.py` with this complete version:
```python
import uuid
from typing import Any, Sequence

import mssql_python
from agent_framework import BaseHistoryProvider, Message

DB_CONFIG = {"server": "localhost", "port": 1433, "user": "sa", "password": "YourStrong!Passw0rd", "database": "agentdb"}


def get_conn(database: str = "agentdb"):
    cfg = DB_CONFIG
    conn_str = f"Server={cfg['server']},{cfg['port']};Database={database};UID={cfg['user']};PWD={{{cfg['password']}}};TrustServerCertificate=yes"
    return mssql_python.connect(conn_str)


def init_db() -> None:
    master = get_conn("master")
    master.setautocommit(True)
    cur = master.cursor()
    cur.execute("IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'agentdb') BEGIN CREATE DATABASE agentdb END")
    master.close()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='Users') BEGIN CREATE TABLE Users (Id INT IDENTITY PRIMARY KEY, Username NVARCHAR(100) UNIQUE NOT NULL, DisplayName NVARCHAR(200) NOT NULL) END")
    cur.execute("IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='Sessions') BEGIN CREATE TABLE Sessions (Id NVARCHAR(100) PRIMARY KEY, UserId INT NOT NULL FOREIGN KEY REFERENCES Users(Id), CreatedAt DATETIME2 DEFAULT GETUTCDATE(), LastActiveAt DATETIME2 DEFAULT GETUTCDATE()) END")
    cur.execute("IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='ChatHistory') BEGIN CREATE TABLE ChatHistory (Id INT IDENTITY PRIMARY KEY, SessionId NVARCHAR(100) NOT NULL FOREIGN KEY REFERENCES Sessions(Id), Role NVARCHAR(50) NOT NULL, Content NVARCHAR(MAX) NOT NULL, CreatedAt DATETIME2 DEFAULT GETUTCDATE()) END")
    cur.execute("IF NOT EXISTS (SELECT 1 FROM Users WHERE Username='marla') INSERT INTO Users (Username, DisplayName) VALUES ('marla', 'Marla')")
    cur.execute("IF NOT EXISTS (SELECT 1 FROM Users WHERE Username='steve') INSERT INTO Users (Username, DisplayName) VALUES ('steve', 'Steve')")
    conn.commit()
    conn.close()


def get_user(username: str) -> dict | None:
    conn = get_conn(); cur = conn.cursor(); cur.execute("SELECT Id, Username, DisplayName FROM Users WHERE Username = ?", (username,)); row = cur.fetchone(); conn.close()
    return {"id": row[0], "username": row[1], "display_name": row[2]} if row else None


def get_or_create_session(user_id: int) -> str:
    conn = get_conn(); cur = conn.cursor(); cur.execute("SELECT TOP 1 Id FROM Sessions WHERE UserId = ? ORDER BY LastActiveAt DESC", (user_id,)); row = cur.fetchone()
    if row:
        session_id = row[0]; cur.execute("UPDATE Sessions SET LastActiveAt = GETUTCDATE() WHERE Id = ?", (session_id,))
    else:
        session_id = str(uuid.uuid4()); cur.execute("INSERT INTO Sessions (Id, UserId) VALUES (?, ?)", (session_id, user_id))
    conn.commit(); conn.close(); return session_id


def get_session_history(session_id: str) -> list[dict]:
    conn = get_conn(); cur = conn.cursor(); cur.execute("SELECT Role, Content FROM ChatHistory WHERE SessionId = ? ORDER BY CreatedAt", (session_id,)); rows = cur.fetchall(); conn.close()
    return [{"role": role, "content": content} for role, content in rows]


class CommerceHistoryProvider(BaseHistoryProvider):
    def __init__(self, source_id: str = "commerce-history"):
        super().__init__(source_id)

    async def get_messages(self, session_id: str | None, *, state: dict[str, Any] | None = None, **kwargs: Any) -> list[Message]:
        if not session_id:
            return []
        return [Message(role=row["role"], text=row["content"]) for row in get_session_history(session_id)]

    async def save_messages(self, session_id: str | None, messages: Sequence[Message], *, state: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if not session_id:
            return
        conn = get_conn(); cur = conn.cursor()
        for msg in messages:
            text = msg.text or ""
            if not text and msg.contents:
                text = "".join(part.text for part in msg.contents if hasattr(part, "text"))
            cur.execute("INSERT INTO ChatHistory (SessionId, Role, Content) VALUES (?, ?, ?)", (session_id, msg.role, text))
        conn.commit(); conn.close()
```

What this adds:
- `Users` for known people
- `Sessions` linked to each user
- `ChatHistory.SessionId` as a foreign key to `Sessions`
- seeded users: **Marla** and **Steve**
- helpers: `get_user()`, `get_or_create_session()`, `get_session_history()`

---
## 🛍️ Step 2 — Create the Product Catalog
Create `products.py`:
```python
PRODUCTS = [
    {"id": 1, "name": "Classic Leather Jacket", "category": "clothing", "tags": ["jacket", "leather", "outerwear", "fashion"], "price": 189.99, "emoji": "🧥"},
    {"id": 2, "name": "Trail Hiking Boots", "category": "footwear", "tags": ["boots", "hiking", "outdoor", "rugged"], "price": 159.99, "emoji": "🥾"},
    {"id": 3, "name": "Organic Cotton Tee", "category": "clothing", "tags": ["shirt", "casual", "basics"], "price": 29.99, "emoji": "👕"},
    {"id": 4, "name": "Wireless Headphones", "category": "electronics", "tags": ["music", "audio", "wireless", "tech"], "price": 249.99, "emoji": "🎧"},
    {"id": 5, "name": "Espresso Machine", "category": "kitchen", "tags": ["coffee", "espresso", "kitchen"], "price": 349.99, "emoji": "☕"},
    {"id": 6, "name": "Yoga Mat", "category": "fitness", "tags": ["yoga", "fitness", "wellness"], "price": 59.99, "emoji": "🧘"},
    {"id": 7, "name": "Mystery Novel", "category": "books", "tags": ["books", "reading", "fiction"], "price": 14.99, "emoji": "📚"},
    {"id": 8, "name": "Smart Fitness Watch", "category": "electronics", "tags": ["fitness", "wearable", "tech"], "price": 199.99, "emoji": "⌚"},
]

KEYWORD_MAP = {"jacket": ["jacket", "leather", "outerwear", "clothing"], "boots": ["boots", "hiking", "outdoor", "footwear"], "coffee": ["coffee", "espresso", "kitchen"], "music": ["music", "audio", "wireless"], "fitness": ["fitness", "wellness", "wearable"], "books": ["books", "reading", "fiction"]}
NEGATIVE_PATTERNS = ["not ", "don't like", "dont like", "hate ", "dislike ", "not into "]

def get_all_products() -> list[dict]:
    return PRODUCTS

def score_products(history: list[dict]) -> list[dict]:
    likes, dislikes = set(), set()
    for text in [item["content"].lower() for item in history if item["role"] == "user"]:
        for keyword, expansions in KEYWORD_MAP.items():
            if keyword in text:
                negative = any(pattern in text and keyword in text[text.find(pattern):text.find(pattern) + 40] for pattern in NEGATIVE_PATTERNS)
                (dislikes if negative else likes).update(expansions)
    likes -= dislikes
    scored = []
    for product in PRODUCTS:
        searchable = set(product["tags"] + [product["category"]] + product["name"].lower().split())
        if searchable & dislikes:
            continue
        score = len(searchable & likes)
        if score > 0:
            scored.append((score, product))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [product for _, product in scored[:6]] if scored else PRODUCTS[:6]
```

How it works:
- `KEYWORD_MAP` expands user language into related tags
- `NEGATIVE_PATTERNS` catches phrases like `don't like boots`
- dislikes win over likes
- the highest keyword overlap becomes the top recommendation

---
## 🌐 Step 3 — Build the API
Create `app.py`:
```python
import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from db import CommerceHistoryProvider, get_or_create_session, get_session_history, get_user, init_db
from products import get_all_products, score_products

async def warmup_model() -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        await client.post("http://localhost:11434/api/generate", json={"model": "llama3.1:latest", "prompt": "hi", "stream": False, "options": {"num_predict": 1}})

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(); await warmup_model(); yield

app = FastAPI(lifespan=lifespan)
provider = CommerceHistoryProvider()
chat_client = OpenAIChatClient(base_url="http://localhost:11434/v1", api_key="not-needed", model_id="llama3.1:latest")
agent = Agent(client=chat_client, instructions="You are a friendly shopping assistant. Ask short follow-up questions and remember preferences.", context_providers=[provider])

class LoginRequest(BaseModel): username: str
class ChatRequest(BaseModel): username: str; message: str
class RecommendationRequest(BaseModel): username: str

@app.post("/api/login")
async def login(req: LoginRequest):
    user = get_user(req.username)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    session_id = get_or_create_session(user["id"])
    return {"user": user, "session_id": session_id, "history": get_session_history(session_id)}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    user = get_user(req.username)
    if not user: raise HTTPException(status_code=401, detail="Not logged in")
    session = agent.create_session(session_id=get_or_create_session(user["id"]))
    return {"response": str(await agent.run(req.message, session=session))}

@app.post("/api/recommendations")
async def recommendations(req: RecommendationRequest):
    user = get_user(req.username)
    if not user: raise HTTPException(status_code=401, detail="Not logged in")
    ranked = score_products(get_session_history(get_or_create_session(user["id"])))
    return {"best_match": ranked[0] if ranked else None, "other": ranked[1:6] if len(ranked) > 1 else []}

@app.get("/api/products")
async def products():
    return {"products": get_all_products()}

@app.get("/")
async def index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
```

Why the warmup helps:
- it sends a tiny request with `num_predict: 1`
- Ollama loads the model before the first real chat request
- the browser feels faster on first use

---
## 🖥️ Step 4 — Build the Frontend
Create `static/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Commerce Agent</title>
  <style>
    body{font-family:Arial,sans-serif;margin:0;background:#f5f7fb;color:#1f2937}.screen,.app{min-height:100vh;display:flex;align-items:center;justify-content:center}.card{background:#fff;border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,.08)}.login{width:420px;padding:32px;text-align:center}.login button,.send-btn,.reco-btn{cursor:pointer;border:0;border-radius:12px;padding:12px 16px;font-weight:700}.login .buttons{display:grid;gap:12px;margin-top:20px}.app{display:none;align-items:stretch;justify-content:stretch}.app.active{display:grid;grid-template-columns:1.5fr 1fr}.panel{padding:20px}.chat-panel{display:flex;flex-direction:column;background:#fff}.messages{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:12px;margin-bottom:16px}.msg{max-width:75%;padding:12px 14px;border-radius:14px;white-space:pre-wrap}.msg.user{align-self:end;background:#2563eb;color:#fff}.msg.assistant{align-self:start;background:#eef2ff}.input-row{display:flex;gap:8px}input{flex:1;padding:12px;border-radius:12px;border:1px solid #cbd5e1}.side-panel{background:#f8fafc;border-left:1px solid #e5e7eb}.products{display:grid;gap:12px;margin-top:16px}.product{background:#fff;border-radius:14px;padding:14px}.muted{color:#6b7280}
  </style>
</head>
<body>
  <div class="screen" id="loginScreen"><div class="card login"><h1>🛍️ Commerce Agent</h1><p class="muted">Pick a sample user to start chatting.</p><div class="buttons"><button onclick="login('marla')">👩 Log in as Marla</button><button onclick="login('steve')">👨 Log in as Steve</button></div></div></div>
  <div class="app" id="app">
    <div class="panel chat-panel"><h2 id="welcomeTitle">Welcome</h2><div class="messages" id="messages"></div><div class="input-row"><input id="messageInput" placeholder="Tell me what you like..." onkeydown="if(event.key==='Enter') sendMessage()" /><button class="send-btn" onclick="sendMessage()">Send</button></div></div>
    <div class="panel side-panel"><h2>✨ Recommendations</h2><p class="muted">Chat first, then ask for product ideas.</p><button class="reco-btn" onclick="loadRecommendations()">Show me recommendations</button><div class="products" id="products"></div></div>
  </div>
  <script>
    let currentUser = null;
    function addMessage(role, content) { const box = document.getElementById('messages'); const item = document.createElement('div'); item.className = `msg ${role}`; item.textContent = content; box.appendChild(item); box.scrollTop = box.scrollHeight; }
    async function login(username) { const res = await fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ username }) }); const data = await res.json(); currentUser = data.user; document.getElementById('welcomeTitle').textContent = `Hi, ${data.user.display_name}!`; document.getElementById('loginScreen').style.display = 'none'; document.getElementById('app').classList.add('active'); document.getElementById('messages').innerHTML = ''; if (data.history.length) { data.history.forEach(item => addMessage(item.role, item.content)); } else { addMessage('assistant', 'Tell me what styles or products you enjoy, and I will learn your taste.'); } }
    async function sendMessage() { const input = document.getElementById('messageInput'); const message = input.value.trim(); if (!message || !currentUser) return; addMessage('user', message); input.value = ''; const res = await fetch('/api/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ username: currentUser.username, message }) }); const data = await res.json(); addMessage('assistant', data.response); }
    async function loadRecommendations() { if (!currentUser) return; const res = await fetch('/api/recommendations', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ username: currentUser.username }) }); const data = await res.json(); const products = document.getElementById('products'); products.innerHTML = ''; [data.best_match, ...(data.other || [])].filter(Boolean).forEach(product => { const div = document.createElement('div'); div.className = 'product'; div.innerHTML = `<div><strong>${product.emoji} ${product.name}</strong></div><div class="muted">${product.category} • ${product.tags.join(', ')}</div><div><strong>$${product.price.toFixed(2)}</strong></div>`; products.appendChild(div); }); }
  </script>
</body>
</html>
```

This UI is intentionally small but fully functional:
- login screen with user buttons
- chat panel for the conversation
- recommendations panel with one button

---
## ▶️ Step 5 — Run It
Start the app:
```bash
uv run uvicorn app:app --reload
```
Open `http://localhost:8000`.

Try this flow:
1. Log in as **Steve**
2. Chat about jackets
3. Mention boots or rugged styles
4. Click **Show me recommendations**

Because the app stores chat history in SQL Server, Steve's saved preferences influence the ranking after the conversation.

---
## ✅ Summary
You now have a complete workshop app with:
- Ollama running `llama3.1:latest`
- Microsoft Agent Framework for the agent
- SQL Server for persistent memory
- FastAPI for the backend
- a browser UI for login, chat, and recommendations

Nice work — you built a full end-to-end commerce agent stack. 🚀
