#!/usr/bin/env bash
set -euo pipefail

HERMES_ENV="${HERMES_ENV:-$HOME/.hermes/.env}"
OPENCODE_CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
OPENCODE_KEY_FILE="${OPENCODE_KEY_FILE:-$OPENCODE_CONFIG_DIR/opencode-runtime.key}"
OPENCODE_CONFIG_FILE="${OPENCODE_CONFIG_FILE:-$OPENCODE_CONFIG_DIR/opencode.json}"
OPENCODE_MODEL="${OPENCODE_MODEL:-default}"
OPENCODE_PROVIDER="${OPENCODE_PROVIDER:-opencode-runtime}"
OPENCODE_BASE_URL="${OPENCODE_BASE_URL:-}"
OPENCODE_KEY_ENV_VAR="${OPENCODE_KEY_ENV_VAR:-}"

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

if [[ -n "$OPENCODE_KEY_ENV_VAR" ]]; then
  api_key="$(extract_env_value "$OPENCODE_KEY_ENV_VAR" "$HERMES_ENV")"
else
  for env_key in OPENCODE_API_KEY OPENAI_API_KEY OPENAI_TOKEN DEEPSEEK_API_KEY; do
    api_key="$(extract_env_value "$env_key" "$HERMES_ENV")"
    if [ -n "$api_key" ]; then
      OPENCODE_KEY_ENV_VAR="$env_key"
      break
    fi
  done
fi

if [[ -z "${api_key:-}" ]]; then
  api_key="$(printenv OPENCODE_RUNTIME_KEY 2>/dev/null || true)"
  if [ -n "$api_key" ]; then
    OPENCODE_KEY_ENV_VAR="OPENCODE_RUNTIME_KEY"
  fi
fi

if [ -z "$api_key" ]; then
  echo "No API key variable was found in $HERMES_ENV. Set OPENCODE_KEY_ENV_VAR before running." >&2
  exit 1
fi

if [ -z "$OPENCODE_BASE_URL" ]; then
  OPENCODE_BASE_URL="$(extract_env_value OPENAI_BASE_URL "$HERMES_ENV")"
fi
if [ -z "$OPENCODE_BASE_URL" ]; then
  OPENCODE_BASE_URL="$(extract_env_value OPENAI_API_BASE "$HERMES_ENV")"
fi
if [ -z "$OPENCODE_BASE_URL" ]; then
  OPENCODE_BASE_URL="$(extract_env_value DEEPSEEK_BASE_URL "$HERMES_ENV")"
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
      "name": "opencode-runtime",
      "options": {
        "baseURL": "$OPENCODE_BASE_URL",
        "apiKey": "{file:$OPENCODE_KEY_FILE}"
      },
      "models": {
        "$OPENCODE_MODEL": {
          "name": "Opencode runtime model",
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
