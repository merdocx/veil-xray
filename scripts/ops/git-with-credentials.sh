#!/usr/bin/env bash
# Git с учётными данными из /root/.config/git/veil-xray.credentials (не в репозитории).
set -euo pipefail
CRED_FILE="${VEIL_GIT_CREDENTIALS:-/root/.config/git/veil-xray.credentials}"
if [[ ! -f "$CRED_FILE" ]]; then
  echo "Missing $CRED_FILE — see docs/operations/github-deploy.md" >&2
  exit 1
fi
exec git -c "credential.helper=store --file=${CRED_FILE}" "$@"
