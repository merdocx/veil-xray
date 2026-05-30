#!/usr/bin/env bash
# Краткий статус загрузки узла (baseline + последний SLO + сервисы).
set -euo pipefail

PROD="${VEIL_PROD_DIR:-/opt/veil-xray}"

echo "=== Veil Xray — загрузка сервера ==="
echo "time: $(date -Iseconds)"
echo "host: $(hostname -f 2>/dev/null || hostname)"
echo ""

echo "--- Ресурсы ---"
echo "cpu: $(nproc) cores, load: $(awk '{print $1,$2,$3}' /proc/loadavg)"
free -h | awk '/^Mem:/{print "mem:", $2, "used", $3, "avail", $7}'
df -h / | awk 'NR==2{print "disk:", $2, "used", $3, "avail", $4, "("$5")"}'
echo ""

echo "--- Сервисы (enabled / active) ---"
for u in xray veil-xray-api nginx; do
  en="$(systemctl is-enabled "$u" 2>/dev/null || echo unknown)"
  ac="$(systemctl is-active "$u" 2>/dev/null || echo unknown)"
  printf "  %-16s enabled=%-8s active=%s\n" "$u" "$en" "$ac"
done
echo ""

echo "--- Мониторинг ---"
if [[ -f /etc/cron.d/veil-xray ]]; then
  echo "  cron: /etc/cron.d/veil-xray OK"
else
  echo "  cron: MISSING — run ${PROD}/scripts/ops/install-ops-cron.sh"
fi
if [[ -f /var/log/veil-baseline.log ]]; then
  echo "  baseline (last): $(tail -1 /var/log/veil-baseline.log)"
else
  echo "  baseline: no log yet"
fi
if [[ -f /var/log/veil-slo.log ]]; then
  echo "  slo (last):      $(tail -1 /var/log/veil-slo.log)"
else
  echo "  slo: no log yet — run check-slo.sh"
fi
if [[ -x "${PROD}/scripts/load-protection/check-slo.sh" ]]; then
  "${PROD}/scripts/load-protection/check-slo.sh" >/dev/null 2>&1 || true
  echo "  slo exit code:   $?"
fi
echo ""

echo "--- API / Xray ---"
if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "  api health: OK"
else
  echo "  api health: FAIL"
fi
if /usr/local/bin/xray -test -config /usr/local/etc/xray/config.json >/dev/null 2>&1; then
  echo "  xray config: OK"
else
  echo "  xray config: FAIL"
fi
key_count="$(curl -fsS -H "Authorization: Bearer $(grep '^API_SECRET_KEY=' "${PROD}/.env" | cut -d= -f2)" http://127.0.0.1:8000/api/keys 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("total",0))' 2>/dev/null || echo "?")"
echo "  api keys: ${key_count}"
echo ""

echo "--- Logrotate ---"
for f in veil-ops veil-xray-backup-log veil-xray-api-log; do
  if [[ -f "/etc/logrotate.d/${f}" ]]; then
    echo "  /etc/logrotate.d/${f}: OK"
  else
    echo "  /etc/logrotate.d/${f}: missing"
  fi
done
