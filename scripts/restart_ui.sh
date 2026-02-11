#!/usr/bin/env bash
set -euo pipefail

# Quick UI restart helper:
# - stops old UI process on the target port (and prior pidfile process)
# - starts a fresh `persona-engine ui` instance
#
# Usage:
#   scripts/restart_ui.sh
#   scripts/restart_ui.sh --port 8001 --reload
#   scripts/restart_ui.sh --foreground

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="127.0.0.1"
PORT="8000"
RELOAD="0"
FOREGROUND="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --reload)
      RELOAD="1"
      shift
      ;;
    --foreground)
      FOREGROUND="1"
      shift
      ;;
    -h|--help)
      cat <<EOF
Usage: scripts/restart_ui.sh [--host HOST] [--port PORT] [--reload] [--foreground]

Defaults:
  --host 127.0.0.1
  --port 8000

Behavior:
  Kills any existing process bound to the port, then starts persona-engine ui.
  Background mode writes:
    PID: /tmp/persona_engine_ui_<port>.pid
    Log: /tmp/persona_engine_ui_<port>.log
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

PY_BIN=".venv/bin/python"
CLI_BIN=".venv/bin/persona-engine"
if [[ ! -x "$CLI_BIN" ]]; then
  echo "Missing $CLI_BIN. Activate/install venv first." >&2
  exit 1
fi

PID_FILE="/tmp/persona_engine_ui_${PORT}.pid"
LOG_FILE="/tmp/persona_engine_ui_${PORT}.log"

kill_pid_if_alive() {
  local pid="$1"
  if [[ -n "${pid}" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    sleep 0.25
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  fi
}

# 1) Stop previous pidfile process if present.
if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  kill_pid_if_alive "${old_pid:-}"
fi

# 2) Stop anything still bound to the target port.
if command -v lsof >/dev/null 2>&1; then
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    kill_pid_if_alive "$pid"
  done < <(lsof -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
fi

CMD=("$CLI_BIN" ui "--host" "$HOST" "--port" "$PORT")
if [[ "$RELOAD" == "1" ]]; then
  CMD+=("--reload")
fi

if [[ "$FOREGROUND" == "1" ]]; then
  echo "Starting UI in foreground on http://${HOST}:${PORT}"
  exec "${CMD[@]}"
fi

nohup "${CMD[@]}" >"$LOG_FILE" 2>&1 &
new_pid="$!"
echo "$new_pid" > "$PID_FILE"
sleep 0.35

if kill -0 "$new_pid" >/dev/null 2>&1; then
  echo "UI restarted: http://${HOST}:${PORT}"
  echo "PID: $new_pid"
  echo "Log: $LOG_FILE"
else
  echo "Failed to start UI. Check log: $LOG_FILE" >&2
  exit 1
fi

