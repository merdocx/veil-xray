#!/usr/bin/env bash
# Peak hours MSK for veil-xray (avoid sync-config / API restart).
# Exit 0 = peak, 1 = off-peak. Override: VEIL_FORCE_OFFPEAK=1
set -euo pipefail

if [[ "${VEIL_FORCE_OFFPEAK:-}" == "1" ]]; then
  exit 1
fi

hour="$(TZ=Europe/Moscow date +%H)"
# Daytime peak ~08:00–23:59 MSK (adjust in docs if needed)
if [[ "$hour" -ge 8 && "$hour" -le 23 ]]; then
  exit 0
fi
exit 1
