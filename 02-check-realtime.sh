#!/usr/bin/env bash
# Verify the OpenAI key actually has Realtime access.
# This is the prerequisite with the longest lead time if it fails, so check early.
set -uo pipefail

: "${OPENAI_API_KEY:?Set OPENAI_API_KEY first, e.g. export OPENAI_API_KEY=sk-...}"

echo "==> Key is valid and billing is live?"
http=$(curl -s -o /tmp/models.json -w '%{http_code}' https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY")

if [ "$http" != "200" ]; then
  echo "FAIL (HTTP $http). Common causes:"
  echo "  401 - bad or revoked key"
  echo "  429 - no credit on the account; add funds"
  cat /tmp/models.json
  exit 1
fi
echo "OK"

echo
echo "==> Realtime models visible on this key:"
jq -r '.data[].id' /tmp/models.json | grep -i realtime || {
  echo "NONE FOUND."
  echo "Realtime is not provisioned on this account yet. Usual fixes:"
  echo "  1. Add credit (a funded account is required)"
  echo "  2. Complete organization verification in the OpenAI dashboard"
  echo "  3. Confirm the key's project has Realtime enabled under project permissions"
  exit 1
}

echo
echo "==> Minting an ephemeral session token (the piece that fails silently in browsers)"
# NOTE: OpenAI has moved this endpoint before. If you get a 404, check the current
# Realtime docs for the session/client-secret path and update REALTIME_SESSION_URL
# in bridge/.env to match.
REALTIME_SESSION_URL="${REALTIME_SESSION_URL:-https://api.openai.com/v1/realtime/sessions}"
REALTIME_MODEL="${REALTIME_MODEL:-gpt-realtime}"

resp=$(curl -s -w '\n%{http_code}' "$REALTIME_SESSION_URL" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -H "OpenAI-Beta: realtime=v1" \
  -d "{\"model\":\"$REALTIME_MODEL\"}")

code=$(echo "$resp" | tail -n1)
body=$(echo "$resp" | sed '$d')

if [ "$code" = "200" ] || [ "$code" = "201" ]; then
  echo "OK - ephemeral token minted."
else
  echo "Session mint returned HTTP $code:"
  echo "$body"
  echo
  echo "A 404 here usually means the endpoint path or model name has changed."
  echo "A 403 means the account lacks Realtime access."
fi
