#!/usr/bin/env bash
set -euo pipefail

HERMES_ENV="${HERMES_ENV:-$HOME/.hermes/.env}"
OPENCODE_CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
OPENCODE_KEY_FILE="${OPENCODE_KEY_FILE:-$OPENCODE_CONFIG_DIR/hermes-deepseek.key}"
OPENCODE_CONFIG_FILE="${OPENCODE_CONFIG_FILE:-$OPENCODE_CONFIG_DIR/opencode.json}"
OPENCODE_MODEL="${OPENCODE_MODEL:-deepseek-v4-pro}"
OPENCODE_PROVIDER="${OPENCODE_PROVIDER:-hermes-deepseek}"
OPENCODE_BASE_URL="${OPENCODE_BASE_URL:-https://api.deepseek.com/v1}"

extract_env_value() {
  local key="$1"
  local file="$2"
  awk -F= -v key="$key" '
    $0 ~ "^[[:space:]]*(export[[:space:]]+)?" key "[[:space:]]*=" {
      sub(/^[[:space:]]*export[[:space:]]+/, "", $0)
      sub("^[[:space:]]*" key "[[:space:]]*=[[:space:]]*", "", $0)
      gsub(/^[\"\047]|[\"\047]$/, "", $0)
      print
      exit
    }
  ' "$file"
}

ensure_opencode() {
  if command -v opencode >/dev/null 2>&1; then
    return
  fi
  if [ -x "$HOME/.opencode/bin/opencode" ]; then
    export PATH="$HOME/.opencode/bin:$PATH"
    return
  fi
  curl -fsSL https://opencode.ai/install | bash
  export PATH="$HOME/.opencode/bin:$PATH"
}

if [ ! -f "$HERMES_ENV" ]; then
  echo "Hermes env file not found: $HERMES_ENV" >&2
  exit 1
fi

api_key="$(extract_env_value DEEPSEEK_API_KEY "$HERMES_ENV")"
if [ -z "$api_key" ]; then
  echo "DEEPSEEK_API_KEY was not found in $HERMES_ENV" >&2
  exit 1
fi

ensure_opencode
mkdir -p "$OPENCODE_CONFIG_DIR"

printf '%s\n' "$api_key" > "$OPENCODE_KEY_FILE"
chmod 600 "$OPENCODE_KEY_FILE"

tmp_config="$(mktemp)"
cat > "$tmp_config" <<JSON
{
  "\$schema": "https://opencode.ai/config.json",
  "model": "$OPENCODE_PROVIDER/$OPENCODE_MODEL",
  "small_model": "$OPENCODE_PROVIDER/$OPENCODE_MODEL",
  "provider": {
    "$OPENCODE_PROVIDER": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Hermes DeepSeek",
      "options": {
        "baseURL": "$OPENCODE_BASE_URL",
        "apiKey": "{file:$OPENCODE_KEY_FILE}"
      },
      "models": {
        "$OPENCODE_MODEL": {
          "name": "DeepSeek V4 Pro",
          "limit": {
            "context": 16000,
            "output": 900
          }
        }
      }
    }
  },
  "enabled_providers": [
    "$OPENCODE_PROVIDER"
  ]
}
JSON
mv "$tmp_config" "$OPENCODE_CONFIG_FILE"
chmod 644 "$OPENCODE_CONFIG_FILE"

opencode --version
opencode models "$OPENCODE_PROVIDER"
echo "Configured opencode provider $OPENCODE_PROVIDER with model $OPENCODE_PROVIDER/$OPENCODE_MODEL"
