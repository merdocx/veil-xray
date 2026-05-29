#!/usr/bin/env bash
# Policy levels.0 — значения по Xray docs + VLESS/Reality best practices (2026).
# handshake=4, connIdle=300, bufferSize=256 KiB, uplinkOnly/downlinkOnly per docs.
set -euo pipefail

CONFIG="${XRAY_CONFIG_PATH:-/usr/local/etc/xray/config.json}"
BACKUP_DIR="${VEIL_XRAY_BACKUP_DIR:-/root/veil-xray/backups}"

HANDSHAKE="${POLICY_HANDSHAKE:-4}"
CONN_IDLE="${POLICY_CONN_IDLE:-300}"
BUFFER_SIZE="${POLICY_BUFFER_SIZE:-256}"
UPLINK_ONLY="${POLICY_UPLINK_ONLY:-2}"
DOWNLINK_ONLY="${POLICY_DOWNLINK_ONLY:-5}"

if [[ ! -f "$CONFIG" ]]; then
  echo "Config not found: $CONFIG" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
cp -a "$CONFIG" "${BACKUP_DIR}/config.json.$(date +%Y%m%d-%H%M%S).bak"

export CONFIG HANDSHAKE CONN_IDLE BUFFER_SIZE UPLINK_ONLY DOWNLINK_ONLY
python3 << 'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["CONFIG"])
data = json.loads(path.read_text())
policy = data.setdefault("policy", {}).setdefault("levels", {}).setdefault("0", {})

targets = {
    "handshake": int(os.environ["HANDSHAKE"]),
    "connIdle": int(os.environ["CONN_IDLE"]),
    "bufferSize": int(os.environ["BUFFER_SIZE"]),
    "uplinkOnly": int(os.environ["UPLINK_ONLY"]),
    "downlinkOnly": int(os.environ["DOWNLINK_ONLY"]),
}

for key, val in targets.items():
    old = policy.get(key, "unset")
    policy[key] = val
    print(f"{key}: {old} -> {val}")

# Сохраняем stats-флаги, если уже были включены
policy.setdefault("statsUserUplink", True)
policy.setdefault("statsUserDownlink", True)

path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
PY

/usr/local/bin/xray -test -config "$CONFIG"
echo "OK: run 'systemctl restart xray' to apply (brief VPN disconnect for all users)."
