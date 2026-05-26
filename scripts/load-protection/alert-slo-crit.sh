#!/usr/bin/env bash
# Алерт при level=crit в check-slo.sh (cron каждые 5 мин).
# Дедупликация: повтор не чаще SLO_ALERT_REPEAT_MIN (по умолчанию 30).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SLO_ALERT_ENV:-/etc/veil-slo-alert.env}"
STATE_FILE="${SLO_ALERT_STATE:-/var/lib/veil-slo-alert.state}"
REPEAT_MIN="${SLO_ALERT_REPEAT_MIN:-30}"
LOG="${SLO_LOG:-/var/log/veil-slo.log}"

[[ -f "$ENV_FILE" ]] && set -a && # shellcheck source=/dev/null
  source "$ENV_FILE" && set +a

mkdir -p "$(dirname "$STATE_FILE")"

set +e
"${SCRIPT_DIR}/check-slo.sh"
EC=$?
set -e

[[ "$EC" -eq 2 ]] || exit 0

LINE="$(tail -n 1 "$LOG" 2>/dev/null || true)"
TS_NOW="$(date +%s)"
LAST_TS="0"
if [[ -f "$STATE_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$STATE_FILE" 2>/dev/null || true
  LAST_TS="${last_alert_ts:-0}"
fi

if [[ $((TS_NOW - LAST_TS)) -lt $((REPEAT_MIN * 60)) ]]; then
  exit 0
fi

MSG="veil-slo CRIT: ${LINE}"
logger -t veil-slo "$MSG"

if [[ -n "${SLO_ALERT_WEBHOOK_URL:-}" ]]; then
  payload="$(printf '{"text":"%s"}' "$(echo "$MSG" | sed 's/"/\\"/g')")"
  curl -fsS -m 10 -X POST \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "${SLO_ALERT_WEBHOOK_URL}" >/dev/null 2>&1 || \
    logger -t veil-slo "webhook alert failed"
fi

if [[ -n "${SLO_ALERT_EMAIL:-}" ]] && command -v mail >/dev/null 2>&1; then
  echo "$MSG" | mail -s "veil-slo CRIT $(hostname -s)" "${SLO_ALERT_EMAIL}" 2>/dev/null || true
fi

{
  echo "last_alert_ts=${TS_NOW}"
  echo "last_line=${LINE}"
} >"$STATE_FILE"

exit 0
