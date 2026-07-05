#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WIKI_ROOT="${STONEHENGE_WIKI_ROOT:-$REPO_ROOT/stonehenge-wiki}"
HOST="${STONEHENGE_WIKI_HOST:-127.0.0.1}"
PORT="${STONEHENGE_WIKI_PORT:-8765}"
PID_FILE="${STONEHENGE_WIKI_SERVER_PID_FILE:-$REPO_ROOT/.stonehenge-wiki-server.pid}"
LOG_FILE="${STONEHENGE_WIKI_SERVER_LOG:-$REPO_ROOT/.stonehenge-wiki-server.log}"

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
    *)
      echo "Unknown argument: $1" >&2
      echo "Use: $0 {start|stop|status|restart|tail|help} [--host HOST] [--port PORT] [--wiki-root PATH]" >&2
      exit 1
      ;;
  esac
done

if [[ "$WIKI_ROOT" != /* ]]; then
  WIKI_ROOT="$(cd "$WIKI_ROOT" && pwd)"
fi

USAGE=$(cat <<'EOF'
Usage:
  server.sh [start|stop|status|restart|tail|help] [options]

Commands:
  start    Start Stonehenge Wiki REST service
  stop     Stop the running service
  status   Show process + health status
  restart  Restart the service
  tail     Tail service log
  help     Show this help

Options:
  --host HOST            Bind host (default: 127.0.0.1)
  --port PORT            Bind port (default: 8765)
  --wiki-root PATH       Wiki root directory (default: ./stonehenge-wiki)
  --pid-file PATH        PID file path (default: .stonehenge-wiki-server.pid)
  --log-file PATH        Log file path (default: .stonehenge-wiki-server.log)
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
  local timeout=15
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
  nohup env PYTHONPATH="$REPO_ROOT" python3 -m stonehenge_wiki.cli \
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
  if is_running; then
    local pid
    pid="$(read_pid)"
    echo "Server running (PID: $pid)"
    if check_health; then
      echo "Health check: OK"
      return 0
    fi
    echo "Health check: failed"
    return 1
  fi

  local on_port
  on_port="$(port_listener_pid || true)"
  if [[ -n "$on_port" ]]; then
    echo "Server process is not tracked by local PID file, but port $PORT is in use (PID: $on_port)."
    return 1
  fi

  echo "Server not running."
  return 1
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
