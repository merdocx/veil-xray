#!/usr/bin/env bash
# Деплой veil-xray на production (pull, ops, restart API).
set -euo pipefail

REPO="${VEIL_REPO_DIR:-/root/veil-v2ray}"
cd "$REPO"

git_fn() {
  if [[ -x "${REPO}/scripts/ops/git-with-credentials.sh" ]]; then
    "${REPO}/scripts/ops/git-with-credentials.sh" "$@"
  else
    git "$@"
  fi
}

echo "==> git pull"
git_fn pull --ff-only origin main

echo "==> sysctl"
if [[ -f /etc/sysctl.d/99-veil-tcp.conf ]]; then
  sysctl --system >/dev/null 2>&1 || true
elif [[ -f "${REPO}/scripts/load-protection/sysctl-tcp-tuning.conf" ]]; then
  cp "${REPO}/scripts/load-protection/sysctl-tcp-tuning.conf" /etc/sysctl.d/99-veil-tcp.conf
  sysctl --system >/dev/null 2>&1 || true
fi

echo "==> logrotate"
if [[ -f "${REPO}/scripts/load-protection/logrotate-veil-ops.example" ]]; then
  install -m 644 "${REPO}/scripts/load-protection/logrotate-veil-ops.example" /etc/logrotate.d/veil-ops
fi

echo "==> cron"
"${REPO}/scripts/ops/install-ops-cron.sh"

echo "==> policy connIdle (idempotent)"
if [[ -x "${REPO}/scripts/load-protection/apply-policy-connidle.sh" ]]; then
  current="$(python3 -c "import json; print(json.load(open('/usr/local/etc/xray/config.json'))['policy']['levels']['0'].get('connIdle',0))" 2>/dev/null || echo 0)"
  if [[ "$current" != "1200" ]]; then
    "${REPO}/scripts/load-protection/apply-policy-connidle.sh"
    systemctl restart xray
    sleep 2
  else
    echo "connIdle already 1200"
  fi
fi

echo "==> systemd units"
if [[ -f "${REPO}/scripts/veil-xray-api.service" ]]; then
  install -m 644 "${REPO}/scripts/veil-xray-api.service" /etc/systemd/system/veil-xray-api.service
  systemctl daemon-reload
fi

echo "==> restart veil-xray-api"
systemctl restart veil-xray-api
sleep 2
systemctl is-active veil-xray-api
curl -fsS http://127.0.0.1:8000/health
echo ""
/usr/local/bin/xray -test -config /usr/local/etc/xray/config.json | tail -1

echo "==> deploy done ($(cat "${REPO}/VERSION" 2>/dev/null || echo unknown))"
