#!/usr/bin/env bash
# Optional: drop NEW inbound TCP to Xray listener so existing sessions stay up (step 4).
# Requires nftables, root, and a defined table/chain (see below).
#
# Usage:
#   NFT_TABLE=inet FILTER_TABLE NFT_CHAIN=input stress-mode-nft.sh on
#   stress-mode-nft.sh off
#
# Set PUBLIC_INTERFACE=eth0 if your default route is not inferred.
# LISTEN_PORT must match VLESS Reality (default 443).

set -euo pipefail

LISTEN_PORT="${LISTEN_PORT:-443}"
NFT_TABLE="${NFT_TABLE:-inet}"
NFT_NAME="${NFT_NAME:-veil_stress}"
CHAIN_NAME="${CHAIN_NAME:-input}"

cmd_on() {
  local iface="${PUBLIC_INTERFACE:-}"
  if [[ -z "${iface}" ]]; then
    iface="$(ip route show default 2>/dev/null | awk '/default/ {print $5; exit}')"
  fi
  if [[ -z "${iface}" ]]; then
    echo "Set PUBLIC_INTERFACE or add a default route." >&2
    exit 1
  fi

  nft add table "${NFT_TABLE}" "${NFT_NAME}" 2>/dev/null || true
  if ! nft list chain "${NFT_TABLE}" "${NFT_NAME}" "${CHAIN_NAME}" &>/dev/null; then
    nft "add chain ${NFT_TABLE} ${NFT_NAME} ${CHAIN_NAME} { type filter hook input priority 0 ; policy accept; }"
  fi
  nft flush chain "${NFT_TABLE}" "${NFT_NAME}" "${CHAIN_NAME}" 2>/dev/null || true
  nft add rule "${NFT_TABLE}" "${NFT_NAME}" "${CHAIN_NAME}" iifname "${iface}" tcp dport "${LISTEN_PORT}" ct state new counter drop
  echo "Stress mode ON: new TCP to ${LISTEN_PORT} on ${iface} dropped (established unaffected)."
}

cmd_off() {
  nft delete table "${NFT_TABLE}" "${NFT_NAME}" 2>/dev/null || true
  echo "Stress mode OFF: table ${NFT_TABLE} ${NFT_NAME} removed."
}

case "${1:-}" in
  on) cmd_on ;;
  off) cmd_off ;;
  *)
    echo "Usage: $0 on|off" >&2
    exit 1
    ;;
esac
