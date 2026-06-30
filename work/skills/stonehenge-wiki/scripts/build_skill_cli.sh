#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$SKILL_DIR/cli/Cargo.toml"
BIN_DIR="$SKILL_DIR/bin"

cargo build --release --manifest-path "$MANIFEST" --bin stonehenge-wiki
mkdir -p "$BIN_DIR"

if [[ -f "$SKILL_DIR/cli/target/release/stonehenge-wiki.exe" ]]; then
  cp "$SKILL_DIR/cli/target/release/stonehenge-wiki.exe" "$BIN_DIR/stonehenge-wiki.exe"
else
  cp "$SKILL_DIR/cli/target/release/stonehenge-wiki" "$BIN_DIR/stonehenge-wiki"
  chmod +x "$BIN_DIR/stonehenge-wiki"
fi
