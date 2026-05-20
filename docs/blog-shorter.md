# Give Your E-Commerce App a Memory: A Shorter Build

Most shopping assistants still act like every visit is the first one. Customers share preferences, come back two days later, and have to repeat everything. That breaks the feeling of continuity you want in an e-commerce experience.

In this version, we build a memory-enabled shopping assistant that keeps context across sessions. The stack is simple: Microsoft Agent Framework for the agent runtime, SQL Server for persistent history, and a FastAPI app serving the web UI.

## The Core Problem: Amnesia in E-Commerce

Stateless chat feels fine in demos, but it fails in real customer journeys. People expect continuity, especially when they are comparing products over multiple sessions, narrowing tastes, or returning after a few days to pick up where they left off.

*What if a customer did not have to say, "I told you last week I'm allergic to peanuts," and the app actually knew that?*

That is the real problem with stateless shopping assistants: they forget details that matter. In allergy-sensitive scenarios, that is not just inconvenient, it can break trust fast.

**Monday:**

> Customer: "I'm looking for snacks, but I'm allergic to peanuts."
>
> Bot: "Got it. I'll show you peanut-free options."

**Wednesday:**

> Customer: "Show me more options like we discussed last time."
>
> Bot: "I'm sorry, could you remind me about any allergies or preferences?"

A memory-enabled assistant should do three things well:

- **Converse naturally**: capture customer intent in plain language.
- **Remember across sessions**: persist preferences so users do not repeat themselves.
- **Recommend better over time**: use prior conversations to improve matching.

With that goal in mind, the architecture can stay surprisingly simple.

## Architecture in One View

The app has three layers: UI and API, the agent runtime, and persistent storage. The key design choice is to keep memory behind a provider interface so the agent code stays clean and the storage layer can evolve independently.

![Architecture diagram](./assets/architecture.png)

The important component is the history provider. It loads prior messages before each run and saves new messages after each run, which means the agent itself stays focused on behavior instead of persistence concerns.

## Why Microsoft Agent Framework

Microsoft Agent Framework handles the repetitive plumbing around sessions and context so you can focus on agent behavior. Instead of wiring conversation state into every route and every agent call, you register a provider once and let the framework lifecycle do the rest.

At a minimum, the wiring looks like this:

```python
from agent_framework import Agent, BaseHistoryProvider

class CommerceHistoryProvider(BaseHistoryProvider):
    async def get_messages(self, session_id, **kwargs):
        return load_from_db(session_id)

    async def save_messages(self, session_id, messages, **kwargs):
        save_to_db(session_id, messages)

agent = Agent(
    client=chat_client,
    instructions="You are a friendly shopping assistant.",
    context_providers=[CommerceHistoryProvider()]
)
```

That single `context_providers` registration is what turns a stateless bot into a memory-aware assistant. It is also what keeps the application code readable as the project grows.

## Why SQL Server for Memory

SQL Server is a practical fit because it is easy to run locally and easy to promote to managed Azure SQL without changing your provider contract. You keep the same schema shape and query style while improving reliability, backups, and scale in production.

For this tutorial, you only need three entities:

- **Users**: who is chatting.
- **Sessions**: conversation boundaries per user.
- **ChatHistory**: ordered messages with role and timestamp.

That is enough schema detail for this post. If you want the full solution, including the DDL, check out the repo.

## Request Flow

The runtime flow is straightforward and keeps handlers concise. Your API receives a message, resolves the user session, creates or resumes the matching agent session, and runs the agent.

```python
@app.post("/api/chat")
async def chat(req: ChatRequest):
    user = get_user(req.username)
    session_id = get_or_create_session(user["id"])
    session = agent.create_session(session_id=session_id)
    response = await agent.run(req.message, session=session)
    return {"response": str(response)}
```

Under the hood, the framework loads prior messages before generation and persists the new exchange after generation. That is the whole trick: the route handler stays short, but the model still sees enough history to respond like it remembers the customer.

## Recommendations Get Better with Memory

Once history exists, recommendations become context-aware instead of generic. You can score products against the customer's stated preferences and return a best match plus alternatives.

That means the assistant can respond to messages like "show me more like last time" without losing the thread. It also means recommendations improve as the customer reveals more about materials, styles, budgets, or use cases over time.

Here is the experience with Steve, whose conversation steers the assistant toward outdoor gear and more tailored recommendations:

![Steve chatting with the shopping agent — Foundry provider selected](./assets/steve-foundry.png)

And here is Marla, a different user with different preferences and a separate session history:

![Marla chatting with the shopping agent — Foundry provider selected](./assets/marla-foundry.png)

That separation matters. Memory is only useful if it stays scoped to the right user and session boundaries.

## Local to Cloud, Without Rewrites

You can start with SQL Server in Docker and ship the same design to Azure SQL later. In practice, this is mostly a configuration change, not a rewrite.

- **Same provider pattern**: `get_messages()` and `save_messages()` stay the same.
- **Same query model**: no architectural rewrite for persistence.
- **Better operations in cloud**: managed backups, HA, and scaling.

This is the biggest implementation win: your memory model stays stable while your deployment matures. That gives you a much cleaner path from local prototype to production system.

## Run It

```bash
uv run uvicorn app:app --reload --port 8000
```

Open http://localhost:8000, log in as different users, chat, then return later and ask for recommendations. You should see session-scoped memory in action, with each user getting their own history and recommendation path.

## Next Steps

If you want to go deeper after this shorter walkthrough, these are the best places to continue.

- **Microsoft Agent Framework docs**: https://learn.microsoft.com/en-us/agent-framework/
- **Azure SQL local dev quickstart**: https://learn.microsoft.com/en-us/azure/azure-sql/database/local-dev-experience-dev-containers-quickstart?view=azuresql
- **Foundry Local Python samples**: https://github.com/microsoft/Foundry-Local/tree/main/samples/python
- **Project source code**: https://github.com/softchris/ecommerce-agent-memory
