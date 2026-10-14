#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
elif [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON="$(command -v python3 || true)"
    if [[ -z "$PYTHON" ]]; then
        echo "python3 not found" >&2
        exit 1
    fi
fi

exec "$PYTHON" "$SCRIPT_DIR/lightning.py"
