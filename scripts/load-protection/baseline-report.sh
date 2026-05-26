#!/usr/bin/env bash
# Сводка по baseline + SLO за N дней (для решения по ёмкости / connIdle).
# Usage: baseline-report.sh [days]   (default: 7)
set -euo pipefail

DAYS="${1:-7}"
BASELINE_LOG="${VEIL_BASELINE_LOG:-/var/log/veil-baseline.log}"
SLO_LOG="${VEIL_SLO_LOG:-/var/log/veil-slo.log}"
OUT="${VEIL_BASELINE_REPORT:-/var/log/veil-baseline-report.log}"

since_date="$(date -d "${DAYS} days ago" +%Y-%m-%d)"

report() {
  echo "=== veil baseline report $(date -Iseconds) last ${DAYS}d (since ${since_date}) ==="

  if [[ -f "$BASELINE_LOG" ]]; then
    echo "--- TCP :443 (established) from ${BASELINE_LOG} ---"
    awk -v since="$since_date" '$0 >= since' "$BASELINE_LOG" | grep -oP 'est_tcp_sport_443=\K[0-9]+' | awk '
      {n++; s+=$1; if(NR==1||$1<min) min=$1; if($1>max) max=$1}
      END {
        if(n) printf "samples=%d avg=%.0f min=%d max=%d\n", n, s/n, min, max
        else print "no samples"
      }'

    echo "--- FIN-WAIT-1 :443 (if present in log) ---"
    awk -v since="$since_date" '$0 >= since' "$BASELINE_LOG" | grep -oP 'fin_wait_443=\K[0-9]+' | awk '
      {n++; s+=$1; if($1>max) max=$1}
      END { if(n) printf "samples=%d avg=%.0f max=%d\n", n, s/n, max; else print "no fin_wait field yet" }'

    echo "--- xray RSS KiB ---"
    awk -v since="$since_date" '$0 >= since' "$BASELINE_LOG" | grep -oP 'xray_rss_kb=\K[0-9]+' | awk '
      {n++; s+=$1; if($1>max) max=$1}
      END { if(n) printf "samples=%d avg=%.0f max=%d\n", n, s/n, max }'

    echo "--- MemAvailable MiB ---"
    awk -v since="$since_date" '$0 >= since' "$BASELINE_LOG" | grep -oP 'mem_avail_kb=\K[0-9]+' | awk '
      {n++; s+=$1; if(NR==1||$1<min) min=$1}
      END { if(n) printf "samples=%d avg=%.0f min=%.0f MiB\n", n, s/n, min/1024 }'
  else
    echo "missing ${BASELINE_LOG}"
  fi

  if [[ -f "$SLO_LOG" ]]; then
    echo "--- SLO levels ---"
    awk -v since="$since_date" '$0 >= since' "$SLO_LOG" | grep -oP 'level=\K\w+' | sort | uniq -c | sort -rn
  fi
  echo ""
}

report >>"$OUT"
report
