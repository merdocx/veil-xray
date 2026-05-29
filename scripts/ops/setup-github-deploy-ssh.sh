#!/usr/bin/env bash
# Настройка SSH deploy key для git pull private repo merdocx/veil-xray на production.
set -euo pipefail

KEY_NAME="id_ed25519_veil_xray_deploy"
SSH_DIR="${HOME}/.ssh"
KEY_PATH="${SSH_DIR}/${KEY_NAME}"
REPO_DIR="${VEIL_REPO_DIR:-/root/veil-xray}"
GITHUB_HOST="github.com"
GITHUB_REPO="git@github.com:merdocx/veil-xray.git"

mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

if [[ ! -f "${KEY_PATH}" ]]; then
  ssh-keygen -t ed25519 -f "${KEY_PATH}" -N "" -C "veil-xray-prod-deploy@$(hostname -s)"
  chmod 600 "${KEY_PATH}"
  chmod 644 "${KEY_PATH}.pub"
  echo "Created ${KEY_PATH}"
else
  echo "Key already exists: ${KEY_PATH}"
fi

# GitHub host keys
if ! grep -q "^${GITHUB_HOST} " "${SSH_DIR}/known_hosts" 2>/dev/null; then
  ssh-keyscan -t ed25519,rsa "${GITHUB_HOST}" >> "${SSH_DIR}/known_hosts" 2>/dev/null
  chmod 644 "${SSH_DIR}/known_hosts"
fi

CONFIG_BLOCK="# veil-xray deploy (managed by setup-github-deploy-ssh.sh)
Host ${GITHUB_HOST}
  HostName ${GITHUB_HOST}
  User git
  IdentityFile ${KEY_PATH}
  IdentitiesOnly yes
"

if [[ -f "${SSH_DIR}/config" ]] && grep -q "veil-xray deploy" "${SSH_DIR}/config" 2>/dev/null; then
  echo "SSH config block for veil-xray already present"
else
  printf '\n%s\n' "$CONFIG_BLOCK" >> "${SSH_DIR}/config"
  chmod 600 "${SSH_DIR}/config"
  echo "Appended Host ${GITHUB_HOST} to ${SSH_DIR}/config"
fi

if [[ -d "${REPO_DIR}/.git" ]]; then
  cd "${REPO_DIR}"
  git remote remove veilbot 2>/dev/null || true
  current="$(git remote get-url origin 2>/dev/null || true)"
  if [[ "$current" != "${GITHUB_REPO}" ]]; then
    git remote set-url origin "${GITHUB_REPO}"
    echo "origin -> ${GITHUB_REPO}"
  fi
fi

PUB="${KEY_PATH}.pub"
echo ""
echo "=== Deploy key (add once in GitHub repo Settings → Deploy keys) ==="
echo "Title: veil-xray-prod-$(hostname -s)"
echo "Allow write access: NO (read-only deploy)"
echo ""
cat "${PUB}"
echo ""
echo "Docs: docs/operations/github-deploy.md"
echo ""
echo "Test after adding key:"
echo "  cd ${REPO_DIR} && git fetch origin main"
