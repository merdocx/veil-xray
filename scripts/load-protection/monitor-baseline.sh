#!/usr/bin/env bash
# Append one CSV-like line with host metrics for baseline analysis (step 2).
# Intended for cron every minute. Adjust LISTEN_PORT if Xray uses not 443.

set -euo pipefail

LISTEN_PORT="${LISTEN_PORT:-443}"
TS="$(date -Iseconds)"
LOAD="$(awk '{print $1,$2,$3}' /proc/loadavg)"
NCPU="$(nproc)"

MEM_AVAIL_KB="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
MEM_TOTAL_KB="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"

XRAY_RSS_KB="0"
if pgrep -x xray >/dev/null 2>&1; then
  XRAY_RSS_KB="$(ps -C xray -o rss= 2>/dev/null | awk '{s+=$1} END {print s+0}')"
fi

EST_443="0"
FIN_WAIT_443="0"
if command -v ss >/dev/null 2>&1; then
  EST_443="$(ss -tan state established sport = ":${LISTEN_PORT}" 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')"
  FIN_WAIT_443="$(ss -tan sport = ":${LISTEN_PORT}" 2>/dev/null | awk '$1=="FIN-WAIT-1"{c++} END{print c+0}')"
fi

TCP_ORPHAN="$(awk '/^TCP:/ {for (i = 1; i <= NF; i++) if ($i == "orphan") print $(i + 1)}' /proc/net/sockstat)"
TCP_ORPHAN="${TCP_ORPHAN:-0}"

echo "${TS} ncpu=${NCPU} load1_5_15=${LOAD} mem_avail_kb=${MEM_AVAIL_KB} mem_total_kb=${MEM_TOTAL_KB} xray_rss_kb=${XRAY_RSS_KB} est_tcp_sport_${LISTEN_PORT}=${EST_443} fin_wait_${LISTEN_PORT}=${FIN_WAIT_443} tcp_orphan=${TCP_ORPHAN}"
