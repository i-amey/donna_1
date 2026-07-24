"""
Realtime <-> Hermes bridge.

Architecture note that matters more than the code: keep the Realtime session dumb.
It is the ears and mouth - voice activity detection, barge-in, turn-taking. Give it
exactly one tool, `ask_hermes`, and let Hermes own reasoning, memory, skills, and
every real tool call via MCP.

Putting business logic in the Realtime prompt is the mistake that makes a build
look like a demo. It also locks you to one vendor. This split lets you swap the
voice layer without touching the agent.

Endpoints:
  GET  /            operator console (static page)
  POST /session     mint an ephemeral Realtime token for the browser
  POST /ask         run a prompt through Hermes, return text
  GET  /healthz     liveness
"""

import asyncio
import os
import shutil

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
REALTIME_MODEL = os.getenv("REALTIME_MODEL", "gpt-realtime")
# OpenAI has relocated this endpoint before. If /session returns 404, check the
# current Realtime docs and override this in .env rather than editing code.
REALTIME_SESSION_URL = os.getenv(
    "REALTIME_SESSION_URL", "https://api.openai.com/v1/realtime/sessions"
)
HERMES_BIN = os.getenv("HERMES_BIN") or shutil.which("hermes") or "/home/ubuntu/.local/bin/hermes"
HERMES_TIMEOUT = int(os.getenv("HERMES_TIMEOUT", "120"))

VOICE_INSTRUCTIONS = """You are the voice interface to an agent named Hermes.

You do not answer questions yourself and you do not have knowledge of the user's
systems. For anything the user asks you to find out, decide, or do, call the
ask_hermes tool and relay what comes back.

Speak in short sentences. Before a call that will take a moment, say a brief
placeholder like "checking" so the line is not silent. Never read out raw JSON,
file paths, or error traces - summarise them.
"""

TOOLS = [
    {
        "type": "function",
        "name": "ask_hermes",
        "description": (
            "Send an instruction or question to the Hermes agent, which has memory, "
            "skills, shell access, and MCP tools. Use for anything requiring real "
            "action or knowledge of the user's systems."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The full instruction, as a complete sentence with all context.",
                }
            },
            "required": ["prompt"],
        },
    }
]

app = FastAPI(title="Realtime bridge")
app.mount("/static", StaticFiles(directory="static"), name="static")


class AskRequest(BaseModel):
    prompt: str


@app.get("/healthz")
async def healthz():
    return {"ok": True, "hermes": HERMES_BIN, "model": REALTIME_MODEL}


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/session")
async def session():
    """Mint a short-lived token so the browser never sees the real API key."""
    payload = {
        "model": REALTIME_MODEL,
        "instructions": VOICE_INSTRUCTIONS,
        "tools": TOOLS,
        "tool_choice": "auto",
        "turn_detection": {"type": "server_vad", "threshold": 0.5},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            REALTIME_SESSION_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
                "OpenAI-Beta": "realtime=v1",
            },
            json=payload,
        )
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"Session mint failed: {r.text}")
    return r.json()


@app.post("/ask")
async def ask(req: AskRequest):
    """Run one prompt through Hermes and return its text reply.

    `hermes chat -q` is the simplest integration and is enough to ship. If turn
    latency becomes the bottleneck, switch to the gateway's HTTP surface so you
    keep a warm session instead of paying process startup on every turn.
    """
    proc = await asyncio.create_subprocess_exec(
        HERMES_BIN,
        "chat",
        "-q",
        req.prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=HERMES_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(504, "Hermes did not respond in time.")

    if proc.returncode != 0:
        raise HTTPException(500, stderr.decode()[:500] or "Hermes exited with an error.")

    return {"reply": stdout.decode().strip()}
