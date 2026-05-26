#!/usr/bin/env bash
# Осторожное снижение policy.levels.0.connIdle (освобождение TCP).
# Default target: 1200s (20 min), was 1800s (30 min).
set -euo pipefail

CONFIG="${XRAY_CONFIG_PATH:-/usr/local/etc/xray/config.json}"
TARGET="${CONN_IDLE_TARGET:-1200}"
BACKUP_DIR="${VEIL_XRAY_BACKUP_DIR:-/root/veil-v2ray/backups}"

if [[ ! -f "$CONFIG" ]]; then
  echo "Config not found: $CONFIG" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
cp -a "$CONFIG" "${BACKUP_DIR}/config.json.$(date +%Y%m%d-%H%M%S).bak"

python3 << PY
import json
from pathlib import Path

path = Path("${CONFIG}")
data = json.loads(path.read_text())
policy = data.setdefault("policy", {}).setdefault("levels", {}).setdefault("0", {})
old = policy.get("connIdle", "unset")
policy["connIdle"] = int("${TARGET}")
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(f"connIdle: {old} -> {policy['connIdle']}")
PY

/usr/local/bin/xray -test -config "$CONFIG"
echo "OK: run 'systemctl restart xray' to apply (brief VPN disconnect)."
