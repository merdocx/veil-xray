#!/usr/bin/env bash
# Установка cron через /etc/cron.d/veil-xray (идемпотентно).
set -euo pipefail

REPO="${VEIL_REPO_DIR:-/root/veil-xray}"
# Cron и runtime API — из prod-каталога (синхронизируется deploy-prod.sh)
PROD="${VEIL_PROD_DIR:-/opt/veil-xray}"
DEST="/etc/cron.d/veil-xray"

chmod +x "${PROD}/scripts/load-protection/"*.sh "${PROD}/scripts/ops/"*.sh 2>/dev/null || true

cat >"$DEST" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# veil-xray ops (managed by install-ops-cron.sh; runtime ${PROD})
* * * * * root ${PROD}/scripts/load-protection/monitor-baseline.sh >> /var/log/veil-baseline.log 2>&1
*/5 * * * * root ${PROD}/scripts/load-protection/check-slo.sh
*/5 * * * * root ${PROD}/scripts/load-protection/alert-slo-crit.sh
*/5 * * * * root ${PROD}/scripts/load-protection/alert-tcp-pressure.sh
*/5 * * * * root ${PROD}/scripts/ops/auto-restart-xray-on-tcp.sh
0 4 * * * root ${PROD}/scripts/ops/cron-nightly-xray-restart.sh
5 6 * * * root ${PROD}/scripts/load-protection/baseline-report.sh 1 >> /var/log/veil-baseline-report.log 2>&1
10 6 * * 1 root ${PROD}/scripts/load-protection/baseline-report.sh 7 >> /var/log/veil-baseline-report.log 2>&1
0 2 * * * root ${PROD}/scripts/backup_database.sh >> ${PROD}/logs/backup.log 2>&1
EOF

chmod 644 "$DEST"

# Убрать дубликаты из root crontab, если остались от прошлых установок
tmp="$(mktemp)"
crontab -l 2>/dev/null | grep -vE 'monitor-baseline|check-slo\.sh|alert-slo-crit|alert-tcp-pressure|auto-restart-xray-on-tcp|cron-nightly-xray|baseline-report|backup_database' >"$tmp" || true
crontab "$tmp" 2>/dev/null || true
rm -f "$tmp"

echo "Installed ${DEST}:"
cat "$DEST"
