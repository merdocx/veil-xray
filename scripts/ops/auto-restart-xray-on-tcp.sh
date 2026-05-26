#!/usr/bin/env bash
# Условный рестарт Xray при устойчивом давлении FIN-WAIT на :443.
# Гистерезис: FIN_WAIT_CRIT подряд STREAK_REQUIRED раз (cron */5), не чаще 1×/час.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/load-protection"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/slo-thresholds.env"

LOG="${VEIL_TCP_RESTART_LOG:-/var/log/veil-xray-tcp-restart.log}"
STATE="${VEIL_TCP_RESTART_STATE:-/var/lib/veil-xray-tcp-restart.state}"
STREAK_REQUIRED="${TCP_RESTART_STREAK:-3}"
MIN_INTERVAL_S="${TCP_RESTART_MIN_INTERVAL_S:-3600}"
LISTEN_PORT="${LISTEN_PORT:-443}"

FIN_WAIT_443="0"
EST_443="0"
if command -v ss >/dev/null 2>&1; then
  EST_443="$(ss -tan state established sport = ":${LISTEN_PORT}" 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')"
  FIN_WAIT_443="$(ss -tan sport = ":${LISTEN_PORT}" 2>/dev/null | awk '$1=="FIN-WAIT-1"{c++} END{print c+0}')"
fi

mkdir -p "$(dirname "$STATE")"
streak=0
last_restart_ts=0
if [[ -f "$STATE" ]]; then
  # shellcheck source=/dev/null
  source "$STATE" 2>/dev/null || true
  streak="${crit_streak:-0}"
  last_restart_ts="${last_restart_ts:-0}"
fi

TS="$(date -Iseconds)"
trigger=0
if [[ "$FIN_WAIT_443" -gt "${FIN_WAIT_CRIT:-1500}" ]]; then
  streak=$((streak + 1))
else
  streak=0
fi

if [[ "$streak" -ge "$STREAK_REQUIRED" ]]; then
  now_ts="$(date +%s)"
  if [[ $((now_ts - last_restart_ts)) -ge "$MIN_INTERVAL_S" ]]; then
    trigger=1
  fi
fi

if [[ "$trigger" -eq 1 ]]; then
  msg="${TS} restart fin_wait=${FIN_WAIT_443} est=${EST_443} streak=${streak}"
  echo "$msg" >>"$LOG"
  logger -t veil-tcp-restart "$msg"
  if systemctl is-active --quiet xray 2>/dev/null; then
    systemctl restart xray
  else
    logger -t veil-tcp-restart "xray unit not active, skip restart"
  fi
  last_restart_ts="$(date +%s)"
  streak=0
fi

{
  echo "crit_streak=${streak}"
  echo "last_fin_wait=${FIN_WAIT_443}"
  echo "last_est=${EST_443}"
  echo "last_restart_ts=${last_restart_ts}"
  echo "updated_ts=$(date +%s)"
} >"$STATE"

exit 0
