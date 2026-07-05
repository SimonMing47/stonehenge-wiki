#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$WORK_ROOT/.." && pwd)"
PYTHONPATH_DEFAULT="$WORK_ROOT"
WIKI_ROOT="${STONEHENGE_WIKI_ROOT:-$WORK_ROOT/stonehenge-wiki}"
HOST="${STONEHENGE_WIKI_HOST:-127.0.0.1}"
PORT="${STONEHENGE_WIKI_PORT:-8765}"
PID_FILE="${STONEHENGE_WIKI_SERVER_PID_FILE:-$WORK_ROOT/.stonehenge-wiki-server.pid}"
LOG_FILE="${STONEHENGE_WIKI_SERVER_LOG:-$WORK_ROOT/.stonehenge-wiki-server.log}"
HEALTH_TIMEOUT="${STONEHENGE_WIKI_HEALTH_TIMEOUT:-15}"
STATUS_OK=0
STATUS_DEGRADED=1
STATUS_BLOCKED=2
JSON_MODE=0

COMMAND="${1:-start}"
shift || true

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
    --wiki-root)
      WIKI_ROOT="$2"
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
    --json)
      JSON_MODE=1
      shift
      ;;
    --health-timeout)
      HEALTH_TIMEOUT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo "Use: $0 {start|stop|status|restart|inspect|tail|help} [--host HOST] [--port PORT] [--wiki-root PATH]" >&2
      exit 1
      ;;
  esac
done

if [[ "$WIKI_ROOT" != /* ]]; then
  WIKI_ROOT="$(cd "$WIKI_ROOT" && pwd)"
fi

USAGE=$(cat <<'EOF'
Usage:
  server.sh [start|stop|status|restart|inspect|tail|help] [options]

Commands:
  start    Start Stonehenge Wiki REST service
  stop     Stop the running service
  status   Show process + health status
  inspect  Show machine-readable status snapshot
  restart  Restart the service
  tail     Tail service log
  help     Show this help

Options:
  --host HOST            Bind host (default: 127.0.0.1)
  --port PORT            Bind port (default: 8765)
  --wiki-root PATH       Wiki root directory (default: ./stonehenge-wiki)
  --pid-file PATH        PID file path (default: .stonehenge-wiki-server.pid)
  --log-file PATH        Log file path (default: .stonehenge-wiki-server.log)
  --health-timeout SEC   Health wait timeout for start/inspect (default: 15)
  --json                 Output JSON for status/inspect
EOF
)

read_pid() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi

  local pid_raw
  pid_raw="$(sed 's/[^0-9]//g' "$PID_FILE" | tr -d '\n')"
  if [[ -z "$pid_raw" ]]; then
    return 1
  fi

  printf '%s\n' "$pid_raw"
}

is_running() {
  local pid
  pid="$(read_pid || true)"
  if [[ -z "$pid" ]]; then
    return 1
  fi

  if kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

port_listener_pids() {
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi
  lsof -iTCP:"$PORT" -sTCP:LISTEN -n -P -F p 2>/dev/null \
    | awk -F'p' '/^p[0-9]+$/{print $2}'
}

port_listener_pid() {
  port_listener_pids | head -n 1
}

check_health() {
  if ! command -v curl >/dev/null 2>&1; then
    return 1
  fi

  curl -s -m 2 -I -X HEAD "http://$HOST:$PORT/health" | grep -q "200 OK"
}

wait_for_health() {
  local timeout=$HEALTH_TIMEOUT
  local tries=0

  while ((tries < timeout)); do
    if check_health; then
      return 0
    fi
    sleep 0.5
    tries=$((tries + 1))
  done
  return 1
}

is_port_owned_by_pid_file() {
  local pid
  pid="$(read_pid || true)"
  local on_port
  on_port="$(port_listener_pid || true)"

  if [[ -z "$pid" || -z "$on_port" ]]; then
    return 1
  fi

  [[ "$pid" == "$on_port" ]]
}

ensure_port_free_for_this_service() {
  local on_port
  on_port="$(port_listener_pid || true)"
  if [[ -z "$on_port" ]]; then
    return 0
  fi

  if is_port_owned_by_pid_file; then
    return 0
  fi

  local owner_cmd
  owner_cmd="$(ps -p "$on_port" -o command= 2>/dev/null || true)"
  echo "Port $PORT already in use by PID $on_port: ${owner_cmd:-unknown}" >&2
  echo "Set --port/STONEHENGE_WIKI_PORT to another value, or stop that process first." >&2
  return 1
}

start_server() {
  if is_running; then
    if check_health; then
      echo "Server already running with PID $(read_pid)"
      return 0
    fi
    echo "PID file exists but server is not healthy. Replacing it..."
    rm -f "$PID_FILE"
  fi

  if ! ensure_port_free_for_this_service; then
    return 1
  fi

  mkdir -p "$(dirname "$LOG_FILE")"
  nohup env PYTHONPATH="${STONEHENGE_WIKI_PYTHONPATH:-$PYTHONPATH_DEFAULT}" python3 -m stonehenge_wiki.cli \
    --wiki-root "$WIKI_ROOT" --serve --host "$HOST" --port "$PORT" \
    >>"$LOG_FILE" 2>&1 &
  local pid="$!"
  echo "$pid" > "$PID_FILE"

  if wait_for_health; then
    echo "Stonehenge Wiki server started. PID: $(read_pid)"
    echo "  - bind: http://$HOST:$PORT/"
    echo "  - log: $LOG_FILE"
    return 0
  fi

  local on_port_pid
  on_port_pid="$(port_listener_pid || true)"
  if [[ -n "$on_port_pid" ]]; then
    if ! is_running; then
      echo "$on_port_pid" > "$PID_FILE"
    fi
    echo "Stonehenge Wiki server started but health probe timed out. PID file updated: $(read_pid)"
    echo "  - bind: http://$HOST:$PORT/"
    echo "  - log: $LOG_FILE"
    return 0
  fi

  echo "Failed to start server; check $LOG_FILE" >&2
  rm -f "$PID_FILE"
  return 1
}

stop_server() {
  if ! is_running; then
    echo "Server is not running."
    if [[ -f "$PID_FILE" ]]; then
      rm -f "$PID_FILE"
    fi

    local on_port
    on_port="$(port_listener_pid || true)"
    if [[ -n "$on_port" ]]; then
      echo "Port $PORT is currently bound by PID $on_port (no local PID file)."
    fi
    return 0
  fi

  local pid
  pid="$(read_pid)"
  echo "Stopping Stonehenge Wiki server (PID: $pid)..."
  kill "$pid" >/dev/null 2>&1 || true

  local tries=0
  while ((tries < 10)); do
    if is_running; then
      sleep 0.2
      tries=$((tries + 1))
    else
      break
    fi
  done

  if is_running; then
    echo "Graceful stop timeout, forcing termination..."
    kill -9 "$pid" >/dev/null 2>&1 || true
  fi

  rm -f "$PID_FILE"
  echo "Server stopped."
}

status_server() {
  local status_code=0
  local status="degraded"

  status_code=$(status_code)
  if ((status_code == STATUS_OK)); then
    status="ok"
  elif ((status_code == STATUS_DEGRADED)); then
    status="degraded"
  else
    status="blocked"
  fi

  if ((JSON_MODE == 1)); then
    status_server_json "$status_code" "$status"
    return "$status_code"
  fi

  if ((status_code == STATUS_OK)); then
    echo "Server running and healthy."
    return "$STATUS_OK"
  fi

  if ((status_code == STATUS_DEGRADED)); then
    if is_running; then
      local pid
      pid="$(read_pid)"
      echo "Server running but health check failed. PID: $pid"
    else
      local listener_pid
      listener_pid="$(port_listener_pid || true)"
      if [[ -n "$listener_pid" ]]; then
        echo "Server process is not tracked by local PID file, but port $PORT is in use (PID: $listener_pid)."
      else
        echo "Server not running."
      fi
    fi
    return "$STATUS_DEGRADED"
  fi

  echo "Port $PORT is blocked by another process or cannot determine status."
  return "$STATUS_BLOCKED"
}

status_code() {
  if is_running; then
    if check_health; then
      echo "$STATUS_OK"
      return 0
    fi

    echo "$STATUS_DEGRADED"
    return 0
  fi

  local on_port
  on_port="$(port_listener_pid || true)"
  if [[ -n "$on_port" ]]; then
    echo "$STATUS_BLOCKED"
    return 0
  fi

  echo "$STATUS_DEGRADED"
  return 0
}

status_server_json() {
  local status_code="$1"
  local status="$2"
  local pid
  local on_port
  local health="unknown"
  local lstart=""
  local etime=""
  local cpu=""
  local mem=""
  local rss=""
  local command=""

  if is_running; then
    pid="$(read_pid)"
  fi

  if [[ -n "${pid:-}" ]] && check_health; then
    health="ok"
  elif [[ -n "${pid:-}" ]]; then
    health="failed"
  fi

  if [[ -n "${pid:-}" ]]; then
    lstart="$(ps -p "$pid" -o lstart= 2>/dev/null | sed 's/^ *//')"
    etime="$(ps -p "$pid" -o etime= 2>/dev/null | sed 's/^ *//')"
    cpu="$(ps -p "$pid" -o %cpu= 2>/dev/null | sed 's/^ *//')"
    mem="$(ps -p "$pid" -o %mem= 2>/dev/null | sed 's/^ *//')"
    rss="$(ps -p "$pid" -o rss= 2>/dev/null | sed 's/^ *//')"
    command="$(ps -p "$pid" -o command= 2>/dev/null | sed 's/^ *//')"
  fi

  on_port="$(port_listener_pid || true)"

  if ! command -v python3 >/dev/null 2>&1; then
    echo "{\"error\":\"python3 required for JSON mode\"}" >&2
    return 1
  fi

  python3 - "$status_code" "$status" "$pid" "$on_port" "$health" "$lstart" "$etime" "$cpu" "$mem" "$rss" "$command" "$HOST" "$PORT" "$WIKI_ROOT" "$LOG_FILE" "$PID_FILE" <<'PY'
import json
import sys

status_code, status, pid, on_port, health, lstart, etime, cpu, mem, rss, command, host, port, wiki_root, log_file, pid_file = sys.argv[1:]

payload = {
    "server": {
        "host": host,
        "port": int(port),
        "wiki_root": wiki_root,
        "pid_file": pid_file,
        "log_file": log_file,
    },
    "status": {
        "state": status,
        "code": int(status_code),
        "running": bool(pid),
        "pid": pid or None,
        "port_listener_pid": on_port or None,
        "health": health,
        "started_at": lstart or None,
        "elapsed": etime or None,
        "cpu_percent": cpu or None,
        "mem_percent": mem or None,
        "rss_kb": rss or None,
        "command": command or None,
    },
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
PY
}

tail_server() {
  if [[ -f "$LOG_FILE" ]]; then
    tail -f "$LOG_FILE"
  else
    echo "Log file does not exist: $LOG_FILE"
    return 1
  fi
}

case "$COMMAND" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  status)
    status_server
    ;;
  inspect)
    status_server
    ;;
  restart)
    stop_server
    start_server
    ;;
  tail)
    tail_server
    ;;
  help|-h|--help|"")
    printf "%s\n" "$USAGE"
    ;;
  *)
    echo "Unknown command: $COMMAND" >&2
    printf "%s\n" "$USAGE"
    exit 1
    ;;
esac
