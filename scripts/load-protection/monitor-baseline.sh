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
if command -v ss >/dev/null 2>&1; then
  EST_443="$(ss -tan state established sport = ":${LISTEN_PORT}" 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')"
fi

echo "${TS} ncpu=${NCPU} load1_5_15=${LOAD} mem_avail_kb=${MEM_AVAIL_KB} mem_total_kb=${MEM_TOTAL_KB} xray_rss_kb=${XRAY_RSS_KB} est_tcp_sport_${LISTEN_PORT}=${EST_443}"
