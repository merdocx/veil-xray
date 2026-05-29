#!/usr/bin/env bash
# Установка cron через /etc/cron.d/veil-xray (идемпотентно).
set -euo pipefail

REPO="${VEIL_REPO_DIR:-/root/veil-xray}"
DEST="/etc/cron.d/veil-xray"

chmod +x "${REPO}/scripts/load-protection/"*.sh "${REPO}/scripts/ops/"*.sh 2>/dev/null || true

cat >"$DEST" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# veil-xray ops (managed by install-ops-cron.sh)
* * * * * root ${REPO}/scripts/load-protection/monitor-baseline.sh >> /var/log/veil-baseline.log 2>&1
*/5 * * * * root ${REPO}/scripts/load-protection/check-slo.sh
*/5 * * * * root ${REPO}/scripts/load-protection/alert-slo-crit.sh
*/5 * * * * root ${REPO}/scripts/load-protection/alert-tcp-pressure.sh
*/5 * * * * root ${REPO}/scripts/ops/auto-restart-xray-on-tcp.sh
0 4 * * * root ${REPO}/scripts/ops/cron-nightly-xray-restart.sh
5 6 * * * root ${REPO}/scripts/load-protection/baseline-report.sh 1 >> /var/log/veil-baseline-report.log 2>&1
10 6 * * 1 root ${REPO}/scripts/load-protection/baseline-report.sh 7 >> /var/log/veil-baseline-report.log 2>&1
0 2 * * * root ${REPO}/scripts/backup_database.sh >> ${REPO}/logs/backup.log 2>&1
EOF

chmod 644 "$DEST"

# Убрать дубликаты из root crontab, если остались от прошлых установок
tmp="$(mktemp)"
crontab -l 2>/dev/null | grep -vE 'monitor-baseline|check-slo\.sh|alert-slo-crit|alert-tcp-pressure|auto-restart-xray-on-tcp|cron-nightly-xray|baseline-report|backup_database' >"$tmp" || true
crontab "$tmp" 2>/dev/null || true
rm -f "$tmp"

echo "Installed ${DEST}:"
cat "$DEST"
