#!/usr/bin/env bash
# Опционально: отдельный системный пользователь для veil-xray-api (не root).
set -euo pipefail

USER="${VEIL_API_USER:-veil}"
GROUP="${VEIL_API_GROUP:-veil}"

if id "$USER" &>/dev/null; then
  echo "User $USER already exists"
else
  useradd --system --home-dir /opt/veil-xray --shell /usr/sbin/nologin "$USER"
  echo "Created system user $USER"
fi

REPO="${VEIL_REPO_DIR:-/root/veil-xray}"
for d in "$REPO/database" "$REPO/logs"; do
  install -d -o "$USER" -g "$GROUP" -m 750 "$d"
done

echo "See docs/operations/PRODUCTION_RUNBOOK.md for systemd User= migration."
