#!/usr/bin/env bash
# Install Hermes Agent and prove one clean conversation before adding anything else.
set -euo pipefail

echo "==> Installing Hermes Agent"
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# The installer writes the launcher to ~/.local/bin. Service accounts and
# non-login shells often have a PATH that excludes it.
if ! grep -q '.local/bin' "$HOME/.bashrc"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi
export PATH="$HOME/.local/bin:$PATH"

echo "==> Dependency check"
hermes doctor

echo
echo "==> Interactive setup: choose a model provider"
echo "    Requirement: the model must have >=64K context or Hermes rejects it at startup."
hermes setup

echo "==> Sandboxing shell tools"
# Never run an internet-reachable agent with an unsandboxed terminal tool.
hermes config set terminal.backend docker

echo
echo "==> Smoke test"
hermes chat -q "Hello! What tools do you have available?"

cat <<'EOF'

If the smoke test returned a clean answer, you have a working base.
If it did not, STOP HERE and fix it. Do not add the gateway, voice, MCP,
or cron on top of a broken base.

Config lives in:
  ~/.hermes/config.yaml    main settings
  ~/.hermes/.env           API keys
  ~/.hermes/skills/        skill files
  ~/.hermes/logs/          logs

Next: scripts/02-check-realtime.sh
EOF
