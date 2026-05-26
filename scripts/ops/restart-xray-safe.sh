#!/usr/bin/env bash
# Restart Xray with optional peak-hour warning.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if "${SCRIPT_DIR}/is-peak-msk.sh"; then
  echo "WARN: peak hours MSK — users will be disconnected briefly." >&2
fi

echo "Restarting xray..."
systemctl restart xray
sleep 2
systemctl is-active xray
/usr/local/bin/xray -test -config /usr/local/etc/xray/config.json
