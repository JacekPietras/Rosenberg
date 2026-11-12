#!/bin/sh
# Start the installed Kev runtime from a regular macOS Terminal for Metal access.
set -eu
KEV_RUNTIME_DIR="${KEV_RUNTIME_DIR:-/private/tmp/rosenberg-kev}"
export HF_HOME="${HF_HOME:-/private/tmp/rosenberg-kev-models}"
export PYTHONUNBUFFERED=1
export HF_HUB_VERBOSITY=info
if [ ! -x "$KEV_RUNTIME_DIR/.venv/bin/python" ]; then
    echo "Kev runtime missing: $KEV_RUNTIME_DIR/.venv/bin/python" >&2
    exit 1
fi
cd "$KEV_RUNTIME_DIR"
echo "Starting Kev-4B from $KEV_RUNTIME_DIR"
echo "Model cache: $HF_HOME"
echo "Loading Python libraries, then model weights; first startup may download files."
exec .venv/bin/python -u -m kev.serve --run jaredpalmer/kev-4b@v1.0 --host 127.0.0.1 --port 8009 "$@"
