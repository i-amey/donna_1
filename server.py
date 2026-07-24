#!/usr/bin/env python3
"""
Minimal MCP server (stdio transport) for Hermes to consume.

Hermes exposes these to the model as mcp_<server-name>_<tool-name>, so the tool
below arrives as `mcp_ops_record_note`. Register it, confirm it loads, then swap
the tool bodies for whatever the task actually needs.

Run standalone to sanity-check:  python server.py
Register with Hermes:            see config/hermes-config-snippet.yaml
Reload without restarting:       /reload-mcp   (in the Hermes CLI)
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ops")

DB = Path.home() / ".hermes" / "ops.db"
DB.parent.mkdir(parents=True, exist_ok=True)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS notes (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               created_at TEXT NOT NULL,
               topic TEXT NOT NULL,
               body TEXT NOT NULL
           )"""
    )
    return conn


@mcp.tool()
def record_note(topic: str, body: str) -> str:
    """Store a durable note under a topic. Use for anything worth recalling later.

    Args:
        topic: Short label to group the note under, e.g. "deploy" or "billing".
        body: The note content, in full sentences.
    """
    now = datetime.now(timezone.utc).isoformat()
    with _db() as conn:
        cur = conn.execute(
            "INSERT INTO notes (created_at, topic, body) VALUES (?, ?, ?)",
            (now, topic, body),
        )
    return f"Saved note #{cur.lastrowid} under '{topic}'."


@mcp.tool()
def search_notes(query: str, limit: int = 10) -> str:
    """Find stored notes whose topic or body matches a substring.

    Args:
        query: Text to match against topic and body.
        limit: Maximum number of notes to return.
    """
    with _db() as conn:
        rows = conn.execute(
            """SELECT id, created_at, topic, body FROM notes
               WHERE topic LIKE ? OR body LIKE ?
               ORDER BY id DESC LIMIT ?""",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()

    if not rows:
        return f"No notes match '{query}'."

    return json.dumps(
        [{"id": r[0], "created_at": r[1], "topic": r[2], "body": r[3]} for r in rows],
        indent=2,
    )


@mcp.tool()
def host_status() -> str:
    """Report uptime, memory, and disk for the machine the agent runs on."""
    import shutil
    import subprocess

    uptime = subprocess.run(["uptime", "-p"], capture_output=True, text=True).stdout.strip()
    mem = subprocess.run(["free", "-h"], capture_output=True, text=True).stdout.strip()
    total, used, free = shutil.disk_usage("/")
    disk = f"disk: {used // 2**30}G used of {total // 2**30}G, {free // 2**30}G free"
    return f"{uptime}\n{mem}\n{disk}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
