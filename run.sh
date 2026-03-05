#!/bin/bash
# Shell wrapper for launchd — activates venv and runs scorekeeper.
# launchd does not provide a full user environment, so we set HOME explicitly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"

if [ ! -d "$VENV" ]; then
    echo "ERROR: venv not found at $VENV. Run: python3 -m venv venv && pip install -r requirements.txt" >&2
    exit 1
fi

source "$VENV/bin/activate"
cd "$SCRIPT_DIR"
exec python -m scorekeeper.main
