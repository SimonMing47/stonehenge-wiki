#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_DIR="$WORK_DIR/skills/stonehenge-wiki"
MANIFEST="$SKILL_DIR/cli/Cargo.toml"
BIN_DIR="$SKILL_DIR/bin"
OUTPUT_NAME="stonehenge-wiki"
HOST_TARGET=""

declare -a TARGETS=()
declare -a BUILT_OUTPUTS=()
HOST_OUTPUT=""

require_tool() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "error: required command not found: $name" >&2
    exit 1
  fi
}

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

split_targets() {
  local value="$1"
  if [[ -z "${value}" ]]; then
    return 0
  fi

  local token
  for token in ${value//,/ }; do
    token="$(trim "$token")"
    [[ -n "$token" ]] && printf '%s\n' "$token"
  done
}

add_unique_target() {
  local candidate="$1"
  local -n out="$2"

  for existing in "${out[@]}"; do
    if [[ "$existing" == "$candidate" ]]; then
      return
    fi
  done
  out+=("$candidate")
}

target_to_dir() {
  local target="$1"
  local arch os

  arch="${target%%-*}"

  case "$target" in
    *-apple-darwin*) os="darwin" ;;
    *-unknown-linux-gnu*|*-unknown-linux-musl*) os="linux" ;;
    *-pc-windows-gnu|*-pc-windows-msvc) os="windows" ;;
    *)
      if [[ "$target" == "$HOST_TARGET" ]]; then
        os="$(uname -s | tr '[:upper:]' '[:lower:]')"
      else
        os="unknown"
      fi
      ;;
  esac

  printf '%s-%s\n' "$os" "$arch"
}

target_installed() {
  local target="$1"
  if ! command -v rustup >/dev/null 2>&1; then
    return 1
  fi
  rustup target list --installed | tr -d '\r' | grep -qx "$target"
}

build_binary() {
  local target="$1"
  local -a cargo_args=("--release" "--manifest-path" "$MANIFEST" "--bin" "$OUTPUT_NAME")

  if [[ "$target" != "$HOST_TARGET" ]]; then
    cargo_args+=("--target" "$target")
  fi

  cargo build "${cargo_args[@]}"
}

copy_release_binary() {
  local target="$1"
  local output_path="$2"
  local source_dir="$SKILL_DIR/cli/target"
  local source_file

  if [[ "$target" != "$HOST_TARGET" ]]; then
    source_dir="$source_dir/$target/release"
  else
    source_dir="$source_dir/release"
  fi

  if [[ -f "$source_dir/$OUTPUT_NAME" ]]; then
    source_file="$source_dir/$OUTPUT_NAME"
  elif [[ -f "$source_dir/$OUTPUT_NAME.exe" ]]; then
    source_file="$source_dir/$OUTPUT_NAME.exe"
  else
    return 1
  fi

  cp "$source_file" "$output_path"
  chmod +x "$output_path"
}

build_and_copy() {
  local target="$1"
  local target_dir="$2"

  if [[ "$target" != "$HOST_TARGET" ]] && ! target_installed "$target"; then
    echo "[warn] skip $target (rust target not installed on this machine)"
    return 1
  fi

  if build_binary "$target"; then
    mkdir -p "$target_dir"
    if copy_release_binary "$target" "$target_dir/$OUTPUT_NAME"; then
      BUILT_OUTPUTS+=("$target_dir/$OUTPUT_NAME")
      return 0
    fi
  fi
  return 1
}

require_tool cargo
require_tool rustc

HOST_TARGET="$(rustc -Vv | awk -F': ' '/^host:/{print $2}')"
if [[ -z "$HOST_TARGET" ]]; then
  echo "error: unable to detect rust host target." >&2
  exit 1
fi

mkdir -p "$BIN_DIR"

if [[ -n "${STONEHENGE_WIKI_BUILD_TARGETS:-}" ]]; then
  while IFS= read -r target; do
    add_unique_target "$target" TARGETS
  done < <(split_targets "$STONEHENGE_WIKI_BUILD_TARGETS")
fi

if (( ${#TARGETS[@]} == 0 )); then
  TARGETS=("$HOST_TARGET")
fi

for target in "${TARGETS[@]}"; do
  target_dir="$BIN_DIR/$(target_to_dir "$target")"
  if build_and_copy "$target" "$target_dir"; then
    echo "[ok] $target -> $target_dir/$OUTPUT_NAME"
    if [[ "$target" == "$HOST_TARGET" ]]; then
      HOST_OUTPUT="$target_dir/$OUTPUT_NAME"
    fi
  else
    echo "[warn] build failed for $target"
  fi
done

if (( ${#BUILT_OUTPUTS[@]} == 0 )); then
  echo "No CLI binaries were built." >&2
  exit 1
fi

echo "Build outputs:"
for path in "${BUILT_OUTPUTS[@]}"; do
  echo "  $path"
done

if [[ -n "$HOST_OUTPUT" && -f "$HOST_OUTPUT" ]]; then
  ln -sfn "$HOST_OUTPUT" "$BIN_DIR/$OUTPUT_NAME"
  echo "Default CLI alias: $BIN_DIR/$OUTPUT_NAME"
fi
