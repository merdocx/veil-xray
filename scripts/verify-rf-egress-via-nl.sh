#!/bin/bash
# Run on the RF server to confirm: egress via NL SOCKS совпадает с IP релея (EXPECTED_NL_IP).
#
# --- Как читать результат ---
# «Direct egress» — обычный выход в интернет без прокси (как видит вас провайдер / маршрут по умолчанию).
# «Egress via SOCKS» — выход через SOCKS (по умолчанию 77.238.243.136:1080).
# Ожидаемо: во второй строке IP = EXPECTED_NL_IP (по умолчанию 77.238.243.136) → сообщение OK, код выхода 0.
#
# --- Если не так ---
# FAIL: could not get IP via SOCKS — с РФ нет доступа к SOCKS (сеть, UFW на NL, Dante ACL, другой IP
#   клиента, неверный порт).
# WARN: SOCKS egress != expected — SOCKS отвечает, но наружу не IP релея: трафик не через этот SOCKS
#   или split-tunnel / другой исходящий путь.
#
# --- Переменные окружения (при необходимости) ---
#   SOCKS_HOST=77.238.243.136 SOCKS_PORT=1080 ./verify-rf-egress-via-nl.sh
#   EXPECTED_NL_IP=... при другом IP релея.
#
# Usage: bash verify-rf-egress-via-nl.sh
set -euo pipefail

SOCKS_HOST="${SOCKS_HOST:-77.238.243.136}"
SOCKS_PORT="${SOCKS_PORT:-1080}"
EXPECTED_NL_IP="${EXPECTED_NL_IP:-77.238.243.136}"

echo "=== Direct egress (no proxy) ==="
DIRECT_IP=$(curl -4 -fsS --max-time 15 https://api.ipify.org || true)
echo "${DIRECT_IP:-<failed>}"
echo
echo "=== Egress via SOCKS ${SOCKS_HOST}:${SOCKS_PORT} ==="
SOCKS_IP=$(curl -4 -fsS --max-time 15 --socks5-hostname "${SOCKS_HOST}:${SOCKS_PORT}" https://api.ipify.org || true)
echo "${SOCKS_IP:-<failed>}"
echo
if [[ -n "${SOCKS_IP}" && "${SOCKS_IP}" == "${EXPECTED_NL_IP}" ]]; then
  echo "OK: SOCKS path shows NL relay IP (${EXPECTED_NL_IP})."
  exit 0
fi
if [[ -z "${SOCKS_IP}" ]]; then
  echo "FAIL: could not get IP via SOCKS (check UFW, Dante ACL, and SOCKS reachability)."
  exit 2
fi
echo "WARN: SOCKS egress (${SOCKS_IP}) != expected NL (${EXPECTED_NL_IP}). Review routing/split-tunnel."
exit 1
