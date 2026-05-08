# 📘 Lesson 1 — Your First Agent with Microsoft Agent Framework

## 👋 Welcome
In this lesson, you'll build a tiny local agent that talks to **Ollama** through **Microsoft Agent Framework**.
By the end, you'll have a working terminal chat app and a clear mental model for how the pieces fit together.

---
## 🎯 What You'll Learn
- Create a Python project with `uv`
- Install `agent-framework`
- Run `llama3.1:latest` with Ollama
- Configure `OpenAIChatClient`
- Build an `Agent`
- Create a session and run a prompt
- Upgrade the script into an interactive chat loop

---
## 🧰 Prerequisites
| Tool | Why you need it | Install | Verify |
| --- | --- | --- | --- |
| Python 3.12+ | Runs the code | Install from [python.org](https://www.python.org/downloads/) and add it to PATH | `python --version` |
| uv | Creates projects and installs packages | `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"` | `uv --version` |
| Ollama | Runs the local model | Install from [ollama.com/download](https://ollama.com/download) | `ollama --version` |

Pull the model used in this workshop:
```bash
ollama pull llama3.1:latest
```

Verify it is available:
```bash
ollama list
```

---
## 🛠️ Step 1 — Create the Project
Run these commands:
```bash
mkdir hello-agent
cd hello-agent
uv init
uv add agent-framework
```

What happened?
- `mkdir hello-agent` created a new folder
- `cd hello-agent` moved into it
- `uv init` created the project scaffold
- `uv add agent-framework` installed Microsoft Agent Framework

You should now have a `pyproject.toml` file and a ready-to-use project.

---
## ✍️ Step 2 — Write Your First Agent
Create `hello_agent.py`:
```python
import asyncio

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient


async def main() -> None:
    client = OpenAIChatClient(
        base_url="http://localhost:11434/v1",
        api_key="not-needed",
        model_id="llama3.1:latest",
    )

    agent = Agent(
        client=client,
        instructions=(
            "You are a friendly workshop assistant. "
            "Answer clearly and encourage the learner."
        ),
    )

    session = agent.create_session()
    response = await agent.run(
        "Hello! Please introduce yourself.",
        session=session,
    )
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
```

### 🔌 The client
This object connects your Python code to Ollama:
```python
client = OpenAIChatClient(
    base_url="http://localhost:11434/v1",
    api_key="not-needed",
    model_id="llama3.1:latest",
)
```

Why these values matter:
- `base_url` points at Ollama's OpenAI-compatible endpoint
- `api_key="not-needed"` is a placeholder because Ollama is local
- `model_id` chooses the model to run

### 🤖 The agent
This object wraps the client and your instructions:
```python
agent = Agent(
    client=client,
    instructions=(
        "You are a friendly workshop assistant. "
        "Answer clearly and encourage the learner."
    ),
)
```

Think of `instructions` as the agent's job description and tone.

### 🧠 The session
A session keeps conversation state while the program is running:
```python
session = agent.create_session()
response = await agent.run("Hello! Please introduce yourself.", session=session)
```

That means the framework can track the ongoing conversation instead of treating every message as unrelated.

---
## ▶️ Step 3 — Run It
Run the file with:
```bash
uv run hello_agent.py
```

Example output:
```text
Hi! I'm your workshop assistant. I can help you build and test your first commerce agent.
```

💡 **First-run tip:** the first response may be slow because Ollama often needs a moment to load `llama3.1:latest` into memory.

---
## 💬 Step 4 — Add a Chat Loop
Now replace `hello_agent.py` with this interactive version:
```python
import asyncio

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient


async def main() -> None:
    client = OpenAIChatClient(
        base_url="http://localhost:11434/v1",
        api_key="not-needed",
        model_id="llama3.1:latest",
    )

    agent = Agent(
        client=client,
        instructions=(
            "You are a friendly workshop assistant. "
            "Help the user explore products and ideas in a warm, simple way."
        ),
    )

    session = agent.create_session()
    print("Chat with your agent! Type 'quit' to exit.\n")

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in {"quit", "exit"}:
            print("Agent: See you next time! 👋")
            break

        if not user_input:
            continue

        response = await agent.run(user_input, session=session)
        print(f"Agent: {response}\n")


if __name__ == "__main__":
    asyncio.run(main())
```

Run it again:
```bash
uv run hello_agent.py
```

Example conversation:
```text
You: Hi there
Agent: Hello! I'm ready to help.

You: I like jackets and boots
Agent: Nice choice! Are you looking for something rugged, casual, or premium?

You: quit
Agent: See you next time! 👋
```

---
## 🧩 How It Works
### 1. Ollama serves the model
Ollama runs `llama3.1:latest` locally and exposes an API at `http://localhost:11434`.

### 2. `OpenAIChatClient` translates your requests
`OpenAIChatClient` sends chat-style requests to Ollama's OpenAI-compatible endpoint at `http://localhost:11434/v1`.

### 3. `Agent` manages the conversation
The `Agent` combines:
- the model client
- your instructions
- session-aware message handling

### 4. The session holds state
A session keeps the conversation alive for as long as the script is running.
Right now that memory is **in-memory only**.
If you stop the script, the history disappears.

That is exactly what we'll improve in the next lesson.

---
## ✅ Summary
You built your first local agent with:
- Python
- `uv`
- `agent-framework`
- Ollama
- `llama3.1:latest`

You learned how to:
- create a project
- configure `OpenAIChatClient`
- create an `Agent`
- use a session
- build an interactive chat loop

In **Lesson 2**, you'll store chat history in SQL Server so the agent remembers conversations across restarts. 🚀
