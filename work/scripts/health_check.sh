#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_SCRIPT="$SCRIPT_DIR/server.sh"

HOST="${STONEHENGE_WIKI_HOST:-127.0.0.1}"
PORT="${STONEHENGE_WIKI_PORT:-8765}"
PID_FILE="${STONEHENGE_WIKI_SERVER_PID_FILE:-$SCRIPT_DIR/../.stonehenge-wiki-server.pid}"
LOG_FILE="${STONEHENGE_WIKI_SERVER_LOG:-$SCRIPT_DIR/../.stonehenge-wiki-server.log}"
RETRIES="${STONEHENGE_WIKI_HEALTH_RETRIES:-1}"
WAIT_SECONDS="${STONEHENGE_WIKI_HEALTH_WAIT_SECONDS:-0}"
JSON_MODE=0

while (($# > 0)); do
  case "$1" in
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      shift 2
      ;;
    --pid-file)
      PID_FILE="$2"
      shift 2
      ;;
    --log-file)
      LOG_FILE="$2"
      shift 2
      ;;
    --retries)
      RETRIES="$2"
      shift 2
      ;;
    --wait)
      WAIT_SECONDS="$2"
      shift 2
      ;;
    --json)
      JSON_MODE=1
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Usage: $0 [--host HOST] [--port PORT] [--retries N] [--wait N] [--json]" >&2
      exit 1
      ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for health check output parsing." >&2
  exit 2
fi

run_probe() {
  local output
  output="$($SERVER_SCRIPT status --host "$HOST" --port "$PORT" --pid-file "$PID_FILE" --log-file "$LOG_FILE" --json 2>&1)"
  local rc=$?

  LAST_OUTPUT="$output"
  return "$rc"
}

attempt=0
last_rc=2
LAST_OUTPUT="{}"

while ((attempt < RETRIES)); do
  attempt=$((attempt + 1))
  run_rc=0
  set +e
  run_probe
  run_rc=$?
  set -e
  if ((run_rc == 0)); then
    last_rc=0
    break
  fi

  last_rc=$run_rc
  if ((WAIT_SECONDS > 0 && attempt < RETRIES)); then
    sleep "$WAIT_SECONDS"
  fi
done

if [[ "$JSON_MODE" == "1" ]]; then
  echo "$LAST_OUTPUT"
  exit "$last_rc"
fi

case "$last_rc" in
  0)
    echo "Stonehenge Wiki health check: OK (host=$HOST port=$PORT)"
    ;;
  1)
    echo "Stonehenge Wiki health check: DEGRADED (host=$HOST port=$PORT)"
    ;;
  2)
    echo "Stonehenge Wiki health check: BLOCKED (host=$HOST port=$PORT)"
    ;;
  *)
    echo "Stonehenge Wiki health check: UNKNOWN (host=$HOST port=$PORT)"
    last_rc=2
    ;;
esac

python3 - "$last_rc" "$LAST_OUTPUT" <<'PY'
import json
import sys

code, raw = sys.argv[1], sys.argv[2]
status = "unknown"
if code == "0":
    status = "ok"
elif code == "1":
    status = "degraded"
elif code == "2":
    status = "blocked"

try:
    payload = json.loads(raw)
except Exception:
    payload = {}

state = payload.get("status", {}).get("state")
pid = payload.get("status", {}).get("pid")
listener_pid = payload.get("status", {}).get("port_listener_pid")
error = payload.get("error")

if error:
    print(f"error: {error}")
print(f"state: {state or status}")
if pid:
    print(f"pid: {pid}")
if listener_pid:
    print(f"listener_pid: {listener_pid}")
PY

exit "$last_rc"
