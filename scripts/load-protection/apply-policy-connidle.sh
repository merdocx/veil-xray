#!/usr/bin/env bash
# Deprecated wrapper: используйте apply-policy-recommended.sh (connIdle входит в policy).
# Оставлено для совместимости: CONN_IDLE_TARGET переопределяет только connIdle.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export POLICY_CONN_IDLE="${CONN_IDLE_TARGET:-300}"
exec "${SCRIPT_DIR}/apply-policy-recommended.sh"
