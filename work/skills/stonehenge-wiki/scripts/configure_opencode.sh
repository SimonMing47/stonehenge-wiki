#!/usr/bin/env bash
set -euo pipefail

# The evaluation image is expected to provide the opencode executable. This
# script only creates an opencode provider configuration; it never installs a
# runtime and never reads credentials from another agent's configuration.
OPENCODE_CONFIG_DIR="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
OPENCODE_CONFIG_FILE="${OPENCODE_CONFIG_FILE:-$OPENCODE_CONFIG_DIR/opencode.json}"
OPENCODE_CONFIG_JSONC="${OPENCODE_CONFIG_JSONC:-$OPENCODE_CONFIG_DIR/opencode.jsonc}"
OPENCODE_KEY_FILE="${OPENCODE_KEY_FILE:-$OPENCODE_CONFIG_DIR/opencode-runtime.key}"
OPENCODE_PROVIDER="${OPENCODE_PROVIDER:-zhipu}"
OPENCODE_MODEL="${OPENCODE_MODEL:-glm-5.2}"
OPENCODE_BASE_URL="${OPENCODE_BASE_URL:-https://open.bigmodel.cn/api/coding/paas/v4}"
OPENCODE_API_KEY="${OPENCODE_API_KEY:-}"
OPENCODE_RECONFIGURE="${OPENCODE_RECONFIGURE:-0}"
OPENCODE_VERIFY="${OPENCODE_VERIFY:-0}"

json_escape() {
  local value=$1
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

if ! command -v opencode >/dev/null 2>&1; then
  echo "error: opencode is required but was not found in PATH" >&2
  exit 11
fi

# A preconfigured evaluation runtime is valid and should not be overwritten,
# even when the platform also injects a credential environment variable.
if [[ "$OPENCODE_RECONFIGURE" != "1" ]] && { [[ -s "$OPENCODE_CONFIG_FILE" ]] || [[ -s "$OPENCODE_CONFIG_JSONC" ]]; }; then
  opencode --version
  echo "Existing opencode configuration retained."
  exit 0
fi

if [[ -z "$OPENCODE_API_KEY" && ! -s "$OPENCODE_KEY_FILE" ]]; then
  cat >&2 <<'EOF'
error: no opencode credential is available
Set OPENCODE_API_KEY, or provide a non-empty OPENCODE_KEY_FILE.
If the scoring runtime is already configured, leave OPENCODE_CONFIG_FILE at its existing path.
EOF
  exit 12
fi

mkdir -p "$OPENCODE_CONFIG_DIR"
chmod 700 "$OPENCODE_CONFIG_DIR"

if [[ -n "$OPENCODE_API_KEY" ]]; then
  printf '%s\n' "$OPENCODE_API_KEY" > "$OPENCODE_KEY_FILE"
fi
chmod 600 "$OPENCODE_KEY_FILE"

tmp_config="$(mktemp "$OPENCODE_CONFIG_DIR/.opencode.json.XXXXXX")"
trap 'rm -f "$tmp_config"' EXIT
cat > "$tmp_config" <<JSON
{
  "\$schema": "https://opencode.ai/config.json",
  "model": "$(json_escape "$OPENCODE_PROVIDER")/$(json_escape "$OPENCODE_MODEL")",
  "small_model": "$(json_escape "$OPENCODE_PROVIDER")/$(json_escape "$OPENCODE_MODEL")",
  "provider": {
    "$(json_escape "$OPENCODE_PROVIDER")": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "OpenCode Runtime",
      "options": {
        "baseURL": "$(json_escape "$OPENCODE_BASE_URL")",
        "apiKey": "{file:$(json_escape "$OPENCODE_KEY_FILE")}"
      },
      "models": {
        "$(json_escape "$OPENCODE_MODEL")": {
          "name": "$(json_escape "$OPENCODE_MODEL")",
          "limit": {
            "context": 204800,
            "output": 131072
          }
        }
      }
    }
  },
  "enabled_providers": ["$(json_escape "$OPENCODE_PROVIDER")"]
}
JSON
chmod 600 "$tmp_config"
mv "$tmp_config" "$OPENCODE_CONFIG_FILE"
trap - EXIT

opencode --version
if [[ "$OPENCODE_VERIFY" == "1" ]]; then
  opencode models "$OPENCODE_PROVIDER"
  opencode run --pure --format json "只回复 OK"
fi
echo "Configured opencode model $OPENCODE_PROVIDER/$OPENCODE_MODEL"
