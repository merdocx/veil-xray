#!/usr/bin/env bash
# Подставляет REALITY_PRIVATE_KEY(_B) из .env в /usr/local/etc/xray/config.json.
# Важно: заменять REPLACE_WITH_xray_x25519_PRIVATE_KEY_B до PRIVATE_KEY (без _B).
set -euo pipefail

ENV_FILE="${1:-/opt/veil-xray/.env}"
CONFIG="${XRAY_CONFIG_PATH:-/usr/local/etc/xray/config.json}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env not found: $ENV_FILE" >&2
  exit 1
fi
if [[ ! -f "$CONFIG" ]]; then
  echo "ERROR: xray config not found: $CONFIG" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

PRIV="${REALITY_PRIVATE_KEY:-}"
PRIV_B="${REALITY_PRIVATE_KEY_B:-$PRIV}"
if [[ -z "$PRIV" ]]; then
  echo "ERROR: REALITY_PRIVATE_KEY not set in $ENV_FILE" >&2
  exit 1
fi

python3 << PY
import json
priv_b = """${PRIV_B}"""
priv = """${PRIV}"""
path = """${CONFIG}"""
with open(path) as f:
    text = f.read()
text = text.replace("REPLACE_WITH_xray_x25519_PRIVATE_KEY_B", priv_b)
text = text.replace("REPLACE_WITH_xray_x25519_PRIVATE_KEY", priv)
cfg = json.loads(text)
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
PY

/usr/local/bin/xray -test -config "$CONFIG"
echo "OK: Reality keys applied to $CONFIG"
