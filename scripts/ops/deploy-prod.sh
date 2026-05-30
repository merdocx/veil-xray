#!/usr/bin/env bash
# Деплой veil-xray на production:
#   git pull в VEIL_REPO_DIR (/root/veil-xray)
#   rsync кода в VEIL_PROD_DIR (/opt/veil-xray) — там же БД, .env, venv, работает systemd
set -euo pipefail

REPO="${VEIL_REPO_DIR:-/root/veil-xray}"
PROD="${VEIL_PROD_DIR:-/opt/veil-xray}"

cd "$REPO"

git_fn() {
  if [[ -x "${REPO}/scripts/ops/git-with-credentials.sh" ]]; then
    "${REPO}/scripts/ops/git-with-credentials.sh" "$@"
  else
    git "$@"
  fi
}

sync_repo_to_prod() {
  echo "==> sync ${REPO}/ -> ${PROD}/"
  mkdir -p "${PROD}/database" "${PROD}/logs" "${PROD}/backups"

  rsync -a \
    --exclude='.git/' \
    --exclude='venv/' \
    --exclude='database/' \
    --exclude='logs/' \
    --exclude='backups/' \
    --exclude='.env' \
    --exclude='__pycache__/' \
    --exclude='.pytest_cache/' \
    --exclude='*.pyc' \
    "${REPO}/" "${PROD}/"

  if [[ ! -x "${PROD}/venv/bin/python3" ]]; then
    echo "==> create venv in ${PROD}"
    python3.11 -m venv "${PROD}/venv" 2>/dev/null || python3 -m venv "${PROD}/venv"
  fi

  echo "==> pip install (${PROD})"
  "${PROD}/venv/bin/pip" install -q --upgrade pip
  "${PROD}/venv/bin/pip" install -q -r "${PROD}/requirements.txt"

  echo "synced version: $(cat "${PROD}/VERSION" 2>/dev/null || echo unknown)"
}

if [[ "${VEIL_DEPLOY_SKIP_PULL:-}" == "1" ]]; then
  echo "==> git pull skipped (VEIL_DEPLOY_SKIP_PULL=1)"
else
  echo "==> git pull (${REPO})"
  git_fn pull --ff-only origin main
fi

sync_repo_to_prod

echo "==> sysctl"
if [[ -f /etc/sysctl.d/99-veil-tcp.conf ]]; then
  sysctl --system >/dev/null 2>&1 || true
elif [[ -f "${PROD}/scripts/load-protection/sysctl-tcp-tuning.conf" ]]; then
  cp "${PROD}/scripts/load-protection/sysctl-tcp-tuning.conf" /etc/sysctl.d/99-veil-tcp.conf
  sysctl --system >/dev/null 2>&1 || true
fi

echo "==> logrotate"
if [[ -f "${PROD}/scripts/load-protection/logrotate-veil-ops.example" ]]; then
  install -m 644 "${PROD}/scripts/load-protection/logrotate-veil-ops.example" /etc/logrotate.d/veil-ops
fi
if [[ -f "${PROD}/scripts/logrotate/veil-xray-backup-log.example" ]]; then
  install -m 644 "${PROD}/scripts/logrotate/veil-xray-backup-log.example" /etc/logrotate.d/veil-xray-backup-log
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "WARN: sqlite3 not found — install for backup_database.sh: apt-get install -y sqlite3" >&2
fi

echo "==> cron (runtime ${PROD})"
VEIL_PROD_DIR="$PROD" "${PROD}/scripts/ops/install-ops-cron.sh"

echo "==> policy recommended (idempotent)"
if [[ -x "${PROD}/scripts/load-protection/apply-policy-recommended.sh" ]]; then
  need_apply=0
  for pair in "handshake:4" "connIdle:300" "bufferSize:256"; do
    key="${pair%%:*}"
    want="${pair##*:}"
    current="$(python3 -c "import json; p=json.load(open('/usr/local/etc/xray/config.json'))['policy']['levels']['0']; print(p.get('${key}', ''))" 2>/dev/null || echo "")"
    if [[ "$current" != "$want" ]]; then
      need_apply=1
      break
    fi
  done
  if [[ "$need_apply" -eq 1 ]]; then
    VEIL_XRAY_BACKUP_DIR="${PROD}/backups" "${PROD}/scripts/load-protection/apply-policy-recommended.sh"
    systemctl restart xray
    sleep 2
  else
    echo "policy already at recommended values"
  fi
fi

echo "==> systemd units"
if [[ -f "${PROD}/scripts/veil-xray-api.service" ]]; then
  install -m 644 "${PROD}/scripts/veil-xray-api.service" /etc/systemd/system/veil-xray-api.service
  systemctl daemon-reload
  systemctl enable veil-xray-api 2>/dev/null || true
fi

echo "==> restart veil-xray-api (${PROD})"
systemctl restart veil-xray-api
systemctl is-active veil-xray-api

echo "==> health (startup sync may take up to 60s)"
health_ok=0
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    health_ok=1
    curl -fsS http://127.0.0.1:8000/health
    echo ""
    break
  fi
  sleep 2
done
if [[ "$health_ok" -ne 1 ]]; then
  echo "WARN: /health not ready after 60s — check: journalctl -u veil-xray-api -n 50" >&2
fi
/usr/local/bin/xray -test -config /usr/local/etc/xray/config.json | tail -1

echo "==> deploy done ($(cat "${PROD}/VERSION" 2>/dev/null || echo unknown)) repo=${REPO} prod=${PROD}"
