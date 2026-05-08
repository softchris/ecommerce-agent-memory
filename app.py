import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from db import init_db, get_user, get_or_create_session, get_session_history, CommerceHistoryProvider
from products import get_all_products, get_product_catalog_text, score_products


async def warmup_models():
    """Ping Ollama models to pre-load them into memory."""
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            print("Warming up llama3.1:latest...")
            await client.post("http://localhost:11434/api/generate", json={
                "model": "llama3.1:latest",
                "prompt": "hi",
                "stream": False,
                "options": {"num_predict": 1}
            })
            print("  llama3.1:latest ready ✅")
        except Exception as e:
            print(f"  warmup failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await warmup_models()
    yield

app = FastAPI(lifespan=lifespan)

history_provider = CommerceHistoryProvider()

chat_client = OpenAIChatClient(
    base_url="http://localhost:11434/v1",
    api_key="not-needed",
    model_id="llama3.1:latest"
)

agent = Agent(
    client=chat_client,
    instructions=(
        "You are a friendly shopping assistant. Help users discover products they'll love. "
        "Ask about their interests, hobbies, and preferences. Remember what they tell you. "
        "Be conversational and warm."
    ),
    context_providers=[history_provider]
)


class LoginRequest(BaseModel):
    username: str


class ChatRequest(BaseModel):
    username: str
    message: str


class RecommendationRequest(BaseModel):
    username: str


@app.post("/api/login")
async def login(req: LoginRequest):
    user = get_user(req.username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    session_id = get_or_create_session(user["id"])
    history = get_session_history(session_id)
    return {
        "user": user,
        "session_id": session_id,
        "history": history
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    user = get_user(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")

    session_id = get_or_create_session(user["id"])
    session = agent.create_session(session_id=session_id)

    response = await agent.run(req.message, session=session)
    response_text = str(response)

    return {"response": response_text}


@app.post("/api/recommendations")
async def recommendations(req: RecommendationRequest):
    user = get_user(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")

    session_id = get_or_create_session(user["id"])
    history = get_session_history(session_id)

    if not history:
        all_prods = get_all_products()[:6]
        return {"best_match": all_prods[0], "other": all_prods[1:], "message": "No conversation history yet — here are some popular items!"}

    matched = score_products(history)
    return {
        "best_match": matched[0] if matched else None,
        "other": matched[1:] if len(matched) > 1 else matched,
        "message": f"Based on your preferences, {user['display_name']}!"
    }


@app.get("/api/products")
async def list_products():
    return {"products": get_all_products()}


@app.get("/")
async def index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
