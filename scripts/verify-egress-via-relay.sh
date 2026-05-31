#!/bin/bash
# На входном узле: проверить, что выход через SOCKS-релей даёт IP релея, а не IP входа.
#
# Переменные:
#   RELAY_HOST / SOCKS_HOST     — хост SOCKS (обязательно)
#   SOCKS_PORT                  — порт SOCKS (1080)
#   EXPECTED_RELAY_IP           — ожидаемый внешний IP при выходе через SOCKS
# Usage:
#   RELAY_HOST=<RELAY_IP> EXPECTED_RELAY_IP=<RELAY_IP> bash scripts/verify-egress-via-relay.sh
set -euo pipefail

RELAY_HOST="${RELAY_HOST:-${SOCKS_HOST:-}}"
SOCKS_PORT="${SOCKS_PORT:-1080}"

if [[ -z "${RELAY_HOST}" ]]; then
  echo "Set RELAY_HOST=<relay-ip> (and optionally EXPECTED_RELAY_IP=…)" >&2
  exit 2
fi

EXPECTED_RELAY_IP="${EXPECTED_RELAY_IP:-$RELAY_HOST}"

echo "=== Direct egress (no proxy) ==="
DIRECT_IP=$(curl -4 -fsS --max-time 15 https://api.ipify.org || true)
echo "${DIRECT_IP:-<failed>}"
echo
echo "=== Egress via SOCKS ${RELAY_HOST}:${SOCKS_PORT} ==="
SOCKS_IP=$(curl -4 -fsS --max-time 15 --socks5-hostname "${RELAY_HOST}:${SOCKS_PORT}" https://api.ipify.org || true)
echo "${SOCKS_IP:-<failed>}"
echo
if [[ -n "${SOCKS_IP}" && "${SOCKS_IP}" == "${EXPECTED_RELAY_IP}" ]]; then
  echo "OK: SOCKS path shows relay IP (${EXPECTED_RELAY_IP})."
  exit 0
fi
if [[ -z "${SOCKS_IP}" ]]; then
  echo "FAIL: could not get IP via SOCKS (firewall, SOCKS daemon, ACL, routing)."
  exit 2
fi
echo "WARN: SOCKS egress (${SOCKS_IP}) != expected relay IP (${EXPECTED_RELAY_IP}). Review Xray routing / split-tunnel."
exit 1
