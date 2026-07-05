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

is_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  if [[ -z "$pid" ]] || [[ ! "$pid" =~ ^[0-9]+$ ]]; then
    return 1
  fi
  if kill -0 "$pid" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

start_server() {
  if is_running; then
    echo "Server already running with PID $(cat "$PID_FILE")"
    return 0
  fi
  mkdir -p "$(dirname "$LOG_FILE")"
  nohup env PYTHONPATH="$REPO_ROOT" python3 -m stonehenge_wiki.cli \
    --wiki-root "$WIKI_ROOT" --serve --host "$HOST" --port "$PORT" \
    >>"$LOG_FILE" 2>&1 &
  local pid=$!
  echo "$pid" > "$PID_FILE"
  sleep 0.6
  if is_running; then
    echo "Stonehenge Wiki server started. PID: $pid"
    echo "  - bind: http://$HOST:$PORT/"
    echo "  - log: $LOG_FILE"
  else
    echo "Failed to start server. Check $LOG_FILE" >&2
    return 1
  fi
}

stop_server() {
  if ! is_running; then
    echo "Server is not running."
    rm -f "$PID_FILE"
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  echo "Stopping Stonehenge Wiki server (PID: $pid)..."
  kill "$pid" >/dev/null 2>&1 || true
  for _ in {1..10}; do
    if is_running; then
      sleep 0.2
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
    echo "Server running (PID: $(cat "$PID_FILE"))"
    if command -v curl >/dev/null 2>&1; then
      if curl -s -m 2 -I -X HEAD "http://$HOST:$PORT/health" | grep -q "200 OK"; then
        echo "Health check: OK"
      else
        echo "Health check: failed"
      fi
    else
      echo "curl not installed; skip health check."
    fi
  else
    echo "Server not running."
    return 1
  fi
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
