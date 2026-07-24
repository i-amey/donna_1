# hermes-stack

An always-on voice agent on a single VPS: OpenAI Realtime as the voice layer,
Hermes as the brain, MCP as the hands.

```
browser ──WebRTC──> Realtime API        ears, mouth, VAD, barge-in
                        │ ask_hermes
                        ▼
                  FastAPI bridge        token minting, function-call relay
                        │
                        ▼
                     Hermes             reasoning, memory, skills, cron
                        │
                        ▼
                  MCP servers           the actual capabilities
```

The one design decision worth defending: the Realtime session has exactly one
tool. It does not reason and it does not know anything about your systems. All
of that lives in Hermes. That split is what lets you swap the voice vendor later
without rewriting the agent, and it keeps the voice layer's latency budget clean.

## Order of operations

Run these in sequence. Each one has to pass before the next is worth attempting.

| Step | Command | Gate |
|---|---|---|
| 1 | `scripts/00-bootstrap.sh` | `ufw status` shows active, `node --version` prints 22.x |
| 2 | `scripts/02-check-realtime.sh` | A realtime model is listed and a token mints |
| 3 | `scripts/01-install-hermes.sh` | `hermes chat -q` returns a clean answer |
| 4 | `scripts/03-install-stack.sh` | Both venvs build |
| 5 | Merge `config/hermes-config-snippet.yaml`, `/reload-mcp` | `/tools` lists `mcp_ops_*` |
| 6 | Install systemd units, reboot | Both services return on their own |

Step 2 comes early on purpose. It is the only prerequisite with a lead time
measured in hours rather than minutes — organisation verification and account
funding both gate Realtime access, and neither resolves while you wait.

## Layout

```
scripts/00-bootstrap.sh        system deps, firewall, swap, docker
scripts/01-install-hermes.sh   Hermes install, sandbox, smoke test
scripts/02-check-realtime.sh   proves the key can actually mint a session
scripts/03-install-stack.sh    venvs for the MCP server and bridge

config/hermes-config-snippet.yaml   MCP registration, sandbox, session reset
config/hermes-gateway.service       keeps the agent alive across reboots
config/realtime-bridge.service      keeps the bridge alive across reboots
config/Caddyfile                    TLS termination

mcp/server.py                  stdio MCP server, three example tools
bridge/main.py                 session minting + Hermes relay
bridge/static/index.html       operator console with a live input meter
```

## Local test before wiring the domain

```bash
cd bridge && ./.venv/bin/uvicorn main:app --port 8080
ssh -L 8080:localhost:8080 ubuntu@<your-ip>     # from your laptop
```

Then open `http://localhost:8080`. Browsers allow microphone access on
`localhost` without TLS, so you can validate the whole loop before DNS
propagates. Anything other than localhost needs HTTPS — that is a hard browser
rule, not a configuration you can relax.

## Failure modes, in the order you will hit them

**`/session` returns 404.** OpenAI has relocated the Realtime session endpoint
before. Check the current docs and override `REALTIME_SESSION_URL` in
`bridge/.env` rather than editing `main.py`.

**`/session` returns 403.** The account does not have Realtime access. Funding
and organisation verification are the usual causes.

**Mic meter stays flat.** The page is not on HTTPS or localhost, or the browser
denied permission. The meter exists specifically to answer this question in one
glance instead of three.

**Hermes rejects the model at startup.** It requires at least 64K context. Pick
a different model with `hermes model`.

**Tools do not appear after editing config.** Run `/reload-mcp`. If they are
still missing, run `mcp/.venv/bin/python mcp/server.py` directly and read the
traceback — a crashing server fails silently from Hermes' side.

**Gateway dies overnight.** Check `journalctl -u hermes-gateway -f`. On a 2GB
box this is usually the OOM killer, which is what the swap file in the bootstrap
script is there to prevent.

## Latency

`/ask` shells out to `hermes chat -q`, which pays process startup on every turn.
That is fine for a first working version and it is the right thing to ship first.
If turn latency becomes the complaint, move to the gateway's HTTP surface so a
warm session persists between turns. Do not optimise this before you have the
loop working end to end.

## Security

The agent has shell access and is reachable from the internet. Three things are
not optional:

- `terminal.backend: docker` so shell tools run in a container, not on the host
- No inbound port open except 22, 80, 443
- The real API key never reaches the browser — that is the entire reason the
  bridge mints ephemeral tokens instead of embedding a key in the page

`privacy.redact_pii` is enabled in the config snippet, which scrubs identifiers
before context leaves for the model provider.
