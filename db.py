import mssql_python
from typing import Any, Sequence
from agent_framework import BaseHistoryProvider, Message

DB_CONFIG = {
    "server": "localhost",
    "port": 1433,
    "user": "sa",
    "password": "YourStrong!Passw0rd",
    "database": "agentdb"
}


def get_conn(database="agentdb"):
    cfg = DB_CONFIG
    conn_str = (
        f"Server={cfg['server']},{cfg['port']};"
        f"Database={database};"
        f"UID={cfg['user']};PWD={{{cfg['password']}}};"
        f"TrustServerCertificate=yes"
    )
    return mssql_python.connect(conn_str)


def init_db():
    conn = get_conn("master")
    conn.setautocommit(True)
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = 'agentdb')
        BEGIN
            CREATE DATABASE agentdb
        END
    """)
    conn.close()

    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'Users')
        BEGIN
            CREATE TABLE Users (
                Id INT IDENTITY PRIMARY KEY,
                Username NVARCHAR(100) UNIQUE NOT NULL,
                DisplayName NVARCHAR(200) NOT NULL,
                CreatedAt DATETIME2 DEFAULT GETUTCDATE()
            )
        END
    """)

    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'Sessions')
        BEGIN
            CREATE TABLE Sessions (
                Id NVARCHAR(100) PRIMARY KEY,
                UserId INT NOT NULL FOREIGN KEY REFERENCES Users(Id),
                CreatedAt DATETIME2 DEFAULT GETUTCDATE(),
                LastActiveAt DATETIME2 DEFAULT GETUTCDATE()
            )
        END
    """)

    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'ChatHistory')
        BEGIN
            CREATE TABLE ChatHistory (
                Id INT IDENTITY PRIMARY KEY,
                SessionId NVARCHAR(100) NOT NULL FOREIGN KEY REFERENCES Sessions(Id),
                Role NVARCHAR(50),
                Content NVARCHAR(MAX),
                CreatedAt DATETIME2 DEFAULT GETUTCDATE()
            )
        END
    """)

    # Seed users if not present
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM Users WHERE Username = 'marla')
            INSERT INTO Users (Username, DisplayName) VALUES ('marla', 'Marla')
    """)
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM Users WHERE Username = 'steve')
            INSERT INTO Users (Username, DisplayName) VALUES ('steve', 'Steve')
    """)

    conn.commit()
    conn.close()
    print("Database initialized ✅")


def get_user(username: str) -> dict | None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT Id, Username, DisplayName FROM Users WHERE Username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "display_name": row[2]}
    return None


def get_or_create_session(user_id: int) -> str:
    """Get the most recent session for a user, or create a new one."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT TOP 1 Id FROM Sessions
        WHERE UserId = ?
        ORDER BY LastActiveAt DESC
    """, (user_id,))
    row = cursor.fetchone()

    if row:
        session_id = row[0]
        cursor.execute("UPDATE Sessions SET LastActiveAt = GETUTCDATE() WHERE Id = ?", (session_id,))
        conn.commit()
    else:
        import uuid
        session_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO Sessions (Id, UserId) VALUES (?, ?)",
            (session_id, user_id)
        )
        conn.commit()

    conn.close()
    return session_id


def get_session_history(session_id: str) -> list[dict]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT Role, Content FROM ChatHistory
        WHERE SessionId = ?
        ORDER BY CreatedAt
    """, (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": r, "content": c} for r, c in rows]


class CommerceHistoryProvider(BaseHistoryProvider):
    def __init__(self, source_id: str = "commerce-history"):
        super().__init__(source_id)

    async def get_messages(
        self, session_id: str | None, *, state: dict[str, Any] | None = None, **kwargs: Any
    ) -> list[Message]:
        if not session_id:
            return []
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT Role, Content FROM ChatHistory
            WHERE SessionId = ?
            ORDER BY CreatedAt
        """, (session_id,))
        rows = cursor.fetchall()
        conn.close()
        return [Message(role=role, text=content) for role, content in rows]

    async def save_messages(
        self,
        session_id: str | None,
        messages: Sequence[Message],
        *,
        state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        if not session_id:
            return
        conn = get_conn()
        cursor = conn.cursor()
        for msg in messages:
            text = msg.text or ""
            if not text and msg.contents:
                text = "".join(c.text for c in msg.contents if hasattr(c, "text"))
            cursor.execute(
                "INSERT INTO ChatHistory (SessionId, Role, Content) VALUES (?, ?, ?)",
                (session_id, msg.role, text)
            )
        conn.commit()
        conn.close()
