#!/usr/bin/env bash
# Quick RAM/swap audit for step 6 (human-readable, no changes).

set -euo pipefail

echo "=== /proc/meminfo (key lines) ==="
awk '/^(MemTotal|MemAvailable|SwapTotal|SwapFree):/ {print}' /proc/meminfo

echo ""
echo "=== vm.swappiness ==="
sysctl vm.swappiness 2>/dev/null || echo "sysctl not available"

echo ""
echo "=== top memory processes (RSS) ==="
ps aux --sort=-rss | head -n 8
