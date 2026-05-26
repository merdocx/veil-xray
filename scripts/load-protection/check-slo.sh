#!/usr/bin/env bash
# Сравнение текущих метрик с порогами SLO (slo-thresholds.env). Лог: /var/log/veil-slo.log
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/slo-thresholds.env"

LOG="${SLO_LOG:-/var/log/veil-slo.log}"
TS="$(date -Iseconds)"

LOAD1="$(awk '{print $1}' /proc/loadavg)"
NCPU="$(nproc)"
LOAD_PER_CPU="$(awk -v l="$LOAD1" -v n="$NCPU" 'BEGIN { printf "%.4f", l/n }')"

MEM_AVAIL_KB="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"

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

LEVEL="ok"
REASONS=()

awk_v="$(awk -v a="$LOAD_PER_CPU" -v w="$LOAD1_WARN" -v c="$LOAD1_CRIT" 'BEGIN {
  if (a+0 >= c+0) print "crit"; else if (a+0 >= w+0) print "warn"; else print "ok"
}')"
if [[ "$awk_v" == "crit" ]]; then LEVEL="crit"; REASONS+=("load1_per_cpu=${LOAD_PER_CPU}>=${LOAD1_CRIT}"); elif [[ "$awk_v" == "warn" && "$LEVEL" == "ok" ]]; then LEVEL="warn"; REASONS+=("load1_per_cpu=${LOAD_PER_CPU}>=${LOAD1_WARN}"); fi

if [[ "$MEM_AVAIL_KB" -lt "$MEM_AVAIL_CRIT_KB" ]]; then
  LEVEL="crit"
  REASONS+=("MemAvail=${MEM_AVAIL_KB}<${MEM_AVAIL_CRIT_KB}")
elif [[ "$MEM_AVAIL_KB" -lt "$MEM_AVAIL_WARN_KB" ]]; then
  [[ "$LEVEL" == "ok" ]] && LEVEL="warn"
  REASONS+=("MemAvail=${MEM_AVAIL_KB}<${MEM_AVAIL_WARN_KB}")
fi

if [[ "$XRAY_RSS_KB" -gt "$XRAY_RSS_CRIT_KB" ]]; then
  [[ "$LEVEL" != "crit" ]] && LEVEL="crit"
  REASONS+=("xray_rss=${XRAY_RSS_KB}>${XRAY_RSS_CRIT_KB}")
elif [[ "$XRAY_RSS_KB" -gt "$XRAY_RSS_WARN_KB" ]]; then
  [[ "$LEVEL" == "ok" ]] && LEVEL="warn"
  REASONS+=("xray_rss=${XRAY_RSS_KB}>${XRAY_RSS_WARN_KB}")
fi

if [[ "$EST_443" -gt "$EST_TCP_CRIT" ]]; then
  [[ "$LEVEL" != "crit" ]] && LEVEL="crit"
  REASONS+=("est_${LISTEN_PORT}=${EST_443}>${EST_TCP_CRIT}")
elif [[ "$EST_443" -gt "$EST_TCP_WARN" ]]; then
  [[ "$LEVEL" == "ok" ]] && LEVEL="warn"
  REASONS+=("est_${LISTEN_PORT}=${EST_443}>${EST_TCP_WARN}")
fi

if [[ "${FIN_WAIT_443:-0}" -gt "${FIN_WAIT_CRIT:-1500}" ]]; then
  [[ "$LEVEL" != "crit" ]] && LEVEL="crit"
  REASONS+=("fin_wait_${LISTEN_PORT}=${FIN_WAIT_443}>${FIN_WAIT_CRIT}")
elif [[ "${FIN_WAIT_443:-0}" -gt "${FIN_WAIT_WARN:-800}" ]]; then
  [[ "$LEVEL" == "ok" ]] && LEVEL="warn"
  REASONS+=("fin_wait_${LISTEN_PORT}=${FIN_WAIT_443}>${FIN_WAIT_WARN}")
fi

# Отношение FIN/ESTAB полезно на больших числах, но шумит при малом ESTAB (после рестартов).
if [[ "${EST_443:-0}" -ge 100 && "${FIN_WAIT_443:-0}" -gt 0 ]]; then
  FIN_RATIO="$(awk -v f="${FIN_WAIT_443}" -v e="${EST_443}" 'BEGIN { printf "%.0f", (f/e)*100 }')"
  if [[ "$FIN_RATIO" -gt "${FIN_WAIT_RATIO_CRIT:-200}" ]]; then
    [[ "$LEVEL" != "crit" ]] && LEVEL="crit"
    REASONS+=("fin_wait_ratio=${FIN_RATIO}>${FIN_WAIT_RATIO_CRIT}")
  elif [[ "$FIN_RATIO" -gt "${FIN_WAIT_RATIO_WARN:-150}" ]]; then
    [[ "$LEVEL" == "ok" ]] && LEVEL="warn"
    REASONS+=("fin_wait_ratio=${FIN_RATIO}>${FIN_WAIT_RATIO_WARN}")
  fi
fi

REASON_STR="$(IFS=,; echo "${REASONS[*]:-}")"
LINE="${TS} level=${LEVEL} load1=${LOAD1} load_per_cpu=${LOAD_PER_CPU} ncpu=${NCPU} mem_avail_kb=${MEM_AVAIL_KB} xray_rss_kb=${XRAY_RSS_KB} est_tcp_sport_${LISTEN_PORT}=${EST_443} fin_wait_${LISTEN_PORT}=${FIN_WAIT_443:-0} reasons=${REASON_STR}"
echo "$LINE" >> "$LOG"

# Ненулевой код только при crit (удобно для внешнего алерта)
if [[ "$LEVEL" == "crit" ]]; then
  exit 2
fi
if [[ "$LEVEL" == "warn" ]]; then
  exit 1
fi
exit 0
