import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent_framework import Agent

from db import init_db, get_user, get_or_create_session, get_session_history, CommerceHistoryProvider
from products import get_all_products, get_product_catalog_text, score_products

sys.path.append(str(Path(__file__).resolve().parents[1]))

from llm import create_chat_client, warmup


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await warmup()
    yield

app = FastAPI(lifespan=lifespan)

history_provider = CommerceHistoryProvider()

chat_client = create_chat_client()

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
    provider: str = "keymatch"  # "keymatch", "ollama", or "foundry"


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
        return {"best_match": all_prods[0], "other": all_prods[1:], "message": "No conversation history yet — here are some popular items!", "provider": req.provider}

    if req.provider == "keymatch":
        matched = score_products(history)
    else:
        # Use LLM (ollama or foundry) for recommendations
        matched = await _llm_recommendations(history, req.provider)

    return {
        "best_match": matched[0] if matched else None,
        "other": matched[1:] if len(matched) > 1 else matched,
        "message": f"Based on your preferences, {user['display_name']}!",
        "provider": req.provider
    }


async def _llm_recommendations(history: list[dict], provider: str) -> list[dict]:
    """Use an LLM to score and rank products based on chat history."""
    import os
    original_provider = os.environ.get("LLM_PROVIDER", "")
    os.environ["LLM_PROVIDER"] = provider

    try:
        # Reload the provider module for the selected provider
        from llm import _load_provider_module, get_provider_name
        _load_provider_module.cache_clear()

        client = create_chat_client()
        catalog = get_product_catalog_text()
        user_msgs = " | ".join(m["content"] for m in history if m["role"] == "user")

        prompt = (
            f"Based on these user messages:\n{user_msgs}\n\n"
            f"Rank the best matching products from this catalog (return ONLY the IDs as comma-separated numbers, best first, max 6):\n{catalog}"
        )

        response = await client.complete(prompt)
        response_text = str(response)

        # Parse product IDs from response
        import re
        ids = [int(x) for x in re.findall(r'\d+', response_text)]
        all_products = get_all_products()
        product_map = {p["id"]: p for p in all_products}
        matched = [product_map[pid] for pid in ids if pid in product_map][:6]

        if matched:
            return matched
    except Exception:
        pass
    finally:
        if original_provider:
            os.environ["LLM_PROVIDER"] = original_provider
        else:
            os.environ.pop("LLM_PROVIDER", None)
        _load_provider_module.cache_clear()

    # Fallback to keymatch if LLM fails
    return score_products(history)


@app.get("/api/products")
async def list_products():
    return {"products": get_all_products()}


@app.get("/")
async def index():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
