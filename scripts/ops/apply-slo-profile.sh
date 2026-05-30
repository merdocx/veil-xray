#!/usr/bin/env bash
# Применить профиль порогов SLO: 2g | 4g | auto (по MemTotal).
set -euo pipefail

PROD="${VEIL_PROD_DIR:-/opt/veil-xray}"
LP="${PROD}/scripts/load-protection"
DEST="${LP}/slo-thresholds.env"

profile="${1:-auto}"
if [[ "$profile" == "auto" ]]; then
  mem_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
  if [[ "$mem_kb" -lt 3000000 ]]; then
    profile="2g"
  else
    profile="4g"
  fi
  echo "Detected MemTotal=${mem_kb} KiB → profile=${profile}"
fi

case "$profile" in
  2g) src="${LP}/slo-thresholds-2g.env.example" ;;
  4g) src="${LP}/slo-thresholds-4g.env.example" ;;
  *)
    echo "Usage: $0 [2g|4g|auto]" >&2
    exit 1
    ;;
esac

if [[ ! -f "$src" ]]; then
  echo "ERROR: missing $src" >&2
  exit 1
fi

cp "$src" "$DEST"
chmod 644 "$DEST"
echo "OK: installed ${DEST} from $(basename "$src")"
