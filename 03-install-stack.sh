#!/usr/bin/env bash
# Install the MCP server and the Realtime bridge into isolated venvs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> MCP server venv"
cd "$ROOT/mcp"
python3.11 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

echo "==> Bridge venv"
cd "$ROOT/bridge"
python3.11 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env

cat <<MSG

Installed. Remaining wiring:

  1. Edit bridge/.env and add your OPENAI_API_KEY.
  2. Merge config/hermes-config-snippet.yaml into ~/.hermes/config.yaml,
     correcting the paths to $ROOT.
  3. In the Hermes CLI run /reload-mcp, then confirm with /tools that
     mcp_ops_record_note and friends are listed.
  4. Install the systemd units:
       sudo cp config/*.service /etc/systemd/system/
       sudo systemctl daemon-reload
       sudo systemctl enable --now hermes-gateway realtime-bridge
  5. Point a domain at this box, install Caddy, drop in config/Caddyfile.
  6. Reboot and confirm both services come back on their own.

MSG
