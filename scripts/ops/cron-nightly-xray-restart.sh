#!/usr/bin/env bash
# Плановый рестарт Xray (сброс FIN-WAIT / orphan TCP). Cron: 04:00 MSK.
set -euo pipefail

LOG="${VEIL_XRAY_RESTART_LOG:-/var/log/veil-xray-restart.log}"
REPO="${VEIL_PROD_DIR:-${VEIL_REPO_DIR:-/opt/veil-xray}}"
TS="$(date -Iseconds)"

{
  echo "=== ${TS} nightly xray restart ==="
  "${REPO}/scripts/ops/restart-xray-safe.sh"
  ss -tan '( sport = :443 )' 2>/dev/null | awk 'NR>1{print $1}' | sort | uniq -c || true
  echo "=== done ==="
} >>"$LOG" 2>&1
