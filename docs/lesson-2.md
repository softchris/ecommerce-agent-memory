# 📘 Lesson 2 — Persistent Memory with SQL Server

## 👋 Welcome Back
In lesson 1, your agent could chat, but it forgot everything when the script stopped.
In this lesson, you'll add **SQL Server-backed memory** so the conversation survives restarts.

---
## 🎯 What You'll Learn
- Run SQL Server locally with Docker
- Connect Python to SQL Server with `mssql-python`
- Create a database and history table
- Build a custom `BaseHistoryProvider`
- Load history before each run
- Save new messages after each run
- Reuse a session across app restarts

---
## 🧰 Prerequisites
You need everything from lesson 1, plus Docker.

| Tool | Why you need it | Install | Verify |
| --- | --- | --- | --- |
| Python 3.12+ | Runs the app | Install from [python.org](https://www.python.org/downloads/) | `python --version` |
| uv | Manages packages | `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` | `uv --version` |
| Ollama | Runs the model | Install from [ollama.com/download](https://ollama.com/download) | `ollama --version` |
| Docker Desktop | Runs SQL Server locally | Install from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) | `docker --version` |

Install the SQL driver:
```bash
uv add mssql-python
```
Start SQL Server:
```bash
docker run -d --name sql -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=YourStrong!Passw0rd" -p 1433:1433 -v sqlvolume:/var/opt/mssql mcr.microsoft.com/mssql/server:2022-latest
```
Verify it is running:
```bash
docker ps
```

---
## 🔌 Step 1 — Connect to SQL Server
Create `db.py` with the connection helper first:
```python
import mssql_python

DB_CONFIG = {
    "server": "localhost",
    "port": 1433,
    "user": "sa",
    "password": "YourStrong!Passw0rd",
    "database": "agentdb",
}

def get_conn(database: str = "agentdb"):
    cfg = DB_CONFIG
    conn_str = (
        f"Server={cfg['server']},{cfg['port']};"
        f"Database={database};"
        f"UID={cfg['user']};PWD={{{cfg['password']}}};"
        f"TrustServerCertificate=yes"
    )
    return mssql_python.connect(conn_str)
```

### Why `TrustServerCertificate=yes` matters
The Docker SQL Server image uses a self-signed certificate in local development, so this flag tells the driver to accept that local cert.

### Why the password is wrapped in braces
Because `YourStrong!Passw0rd` contains `!`, write it like this:
```text
PWD={YourStrong!Passw0rd}
```
That protects special characters from being misread.

Connection string format:
```text
Server=localhost,1433;Database=agentdb;UID=sa;PWD={YourStrong!Passw0rd};TrustServerCertificate=yes
```

---
## 🗄️ Step 2 — Create the Database and Tables
Now replace `db.py` with this full version:
```python
from typing import Any, Sequence

import mssql_python
from agent_framework import BaseHistoryProvider, Message

DB_CONFIG = {
    "server": "localhost",
    "port": 1433,
    "user": "sa",
    "password": "YourStrong!Passw0rd",
    "database": "agentdb",
}

def get_conn(database: str = "agentdb"):
    cfg = DB_CONFIG
    conn_str = (
        f"Server={cfg['server']},{cfg['port']};"
        f"Database={database};"
        f"UID={cfg['user']};PWD={{{cfg['password']}}};"
        f"TrustServerCertificate=yes"
    )
    return mssql_python.connect(conn_str)

def init_db() -> None:
    master_conn = get_conn("master")
    master_conn.setautocommit(True)
    cursor = master_conn.cursor()
    cursor.execute("""IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'agentdb') BEGIN CREATE DATABASE agentdb END""")
    master_conn.close()

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'ChatHistory')
        BEGIN
            CREATE TABLE ChatHistory (
                Id INT IDENTITY PRIMARY KEY,
                SessionId NVARCHAR(100) NOT NULL,
                Role NVARCHAR(50) NOT NULL,
                Content NVARCHAR(MAX) NOT NULL,
                CreatedAt DATETIME2 DEFAULT GETUTCDATE()
            )
        END
    """)
    conn.commit()
    conn.close()

class CommerceHistoryProvider(BaseHistoryProvider):
    def __init__(self, source_id: str = "commerce-history"):
        super().__init__(source_id)

    async def get_messages(self, session_id: str | None, *, state: dict[str, Any] | None = None, **kwargs: Any) -> list[Message]:
        if not session_id:
            return []
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT Role, Content FROM ChatHistory WHERE SessionId = ? ORDER BY CreatedAt", (session_id,))
        rows = cursor.fetchall()
        conn.close()
        return [Message(role=role, text=content) for role, content in rows]

    async def save_messages(self, session_id: str | None, messages: Sequence[Message], *, state: dict[str, Any] | None = None, **kwargs: Any) -> None:
        if not session_id:
            return
        conn = get_conn()
        cursor = conn.cursor()
        for msg in messages:
            text = msg.text or ""
            if not text and msg.contents:
                text = "".join(part.text for part in msg.contents if hasattr(part, "text"))
            cursor.execute("INSERT INTO ChatHistory (SessionId, Role, Content) VALUES (?, ?, ?)", (session_id, msg.role, text))
        conn.commit()
        conn.close()
```

### Why `setautocommit(True)` matters
`CREATE DATABASE` cannot run inside a normal transaction, so we connect to `master` and enable autocommit first.

### What the table stores
- `SessionId` groups messages into one conversation
- `Role` stores `user` or `assistant`
- `Content` stores the message text
- `CreatedAt` keeps everything in order

---
## 🧠 Step 3 — Build a History Provider
The provider above is the bridge between Agent Framework and SQL Server.

Important details:
- `super().__init__(source_id)` registers the provider identity
- `get_messages()` loads saved rows and turns them into `Message` objects
- `save_messages()` stores each new message after a run
- it handles both `msg.text` and `msg.contents`

Framework lifecycle:
```text
agent.run(...) starts
  ↓
get_messages(session_id) loads old history
  ↓
Ollama generates a reply
  ↓
save_messages(session_id, messages) stores new history
```

---
## 🔗 Step 4 — Wire It Up
Create `chat_with_memory.py`:
```python
import asyncio

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from db import CommerceHistoryProvider, init_db

async def main() -> None:
    init_db()
    client = OpenAIChatClient(base_url="http://localhost:11434/v1", api_key="not-needed", model_id="llama3.1:latest")
    provider = CommerceHistoryProvider()
    agent = Agent(
        client=client,
        instructions="You are a friendly commerce assistant. Remember what the user likes and keep the conversation warm.",
        context_providers=[provider],
    )
    session_id = "demo-user-session"
    session = agent.create_session(session_id=session_id)
    print("Chat with memory! Type 'quit' to exit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"quit", "exit"}:
            print("Agent: Bye for now! 👋")
            break
        if not user_input:
            continue
        response = await agent.run(user_input, session=session)
        print(f"Agent: {response}\n")

if __name__ == "__main__":
    asyncio.run(main())
```

Important: pass the provider with `context_providers=[provider]`, not `history_provider=`.
Use a fixed `session_id` so the same history is loaded every time the app restarts.

---
## 🧪 Step 5 — Test It
Run the app:
```bash
uv run chat_with_memory.py
```

Try this:
```text
You: My name is Marla and I love leather jackets.
Agent: Nice to meet you, Marla! Leather jackets are a great style choice.

You: quit
Agent: Bye for now! 👋
```

Run it again and ask:
```text
You: What do you remember about me?
Agent: You told me your name is Marla and that you love leather jackets.
```

That persistence is the whole point of this lesson.

---
## ✅ Summary
You built:
- a SQL Server connection helper
- a database initializer
- a `ChatHistory` table
- a custom `CommerceHistoryProvider`
- a chat app with persistent memory

In **Lesson 3**, you'll add a web UI, named users, sessions, and simple product recommendations. 🚀
