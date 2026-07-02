#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST="$SKILL_DIR/cli/Cargo.toml"
BIN_DIR="$SKILL_DIR/bin"
WINDOWS_TARGET="${WINDOWS_TARGET:-x86_64-pc-windows-gnu}"

build_binary() {
  local bin_name="$1"
  local target="${2:-}"

  if [[ -n "$target" ]]; then
    if ! rustup target list --installed | grep -qx "$target"; then
      return 1
    fi
    cargo build --release --manifest-path "$MANIFEST" --target "$target" --bin "$bin_name"
    echo "$target"
    return 0
  fi

  cargo build --release --manifest-path "$MANIFEST" --bin "$bin_name"
  echo ""
}

copy_release_binary() {
  local bin_name="$1"
  local target="${2:-}"
  local output_name="$3"

  local src_base="$SKILL_DIR/cli/target"
  if [[ -n "$target" ]]; then
    src_base="$src_base/$target/release"
  else
    src_base="$src_base/release"
  fi

  if [[ -f "$src_base/$bin_name" ]]; then
    cp "$src_base/$bin_name" "$BIN_DIR/$output_name"
    chmod +x "$BIN_DIR/$output_name"
    return 0
  fi

  if [[ -f "$src_base/$bin_name.exe" ]]; then
    cp "$src_base/$bin_name.exe" "$BIN_DIR/$output_name"
    chmod +x "$BIN_DIR/$output_name"
    return 0
  fi

  return 1
}

mkdir -p "$BIN_DIR"

echo "[1/4] build universal Stonehenge CLI"
build_binary stonehenge-wiki
copy_release_binary stonehenge-wiki "" stonehenge-wiki

echo "[2/4] build Linux CLI alias"
build_binary stonehenge-wiki-linux
copy_release_binary stonehenge-wiki-linux "" stonehenge-wiki-linux

echo "[3/4] build Windows CLI alias"
if built_target="$(build_binary stonehenge-wiki-windows "$WINDOWS_TARGET" 2>/dev/null)"; then
  target_for_windows="$(if [[ -n "${built_target}" ]]; then echo "$WINDOWS_TARGET"; else echo ""; fi)"
  if copy_release_binary stonehenge-wiki-windows "$target_for_windows" stonehenge-wiki-windows.exe; then
    echo "windows binary: $BIN_DIR/stonehenge-wiki-windows.exe"
  else
    if copy_release_binary stonehenge-wiki-windows "" stonehenge-wiki-windows.exe; then
      echo "warning: windows target cross-build unavailable; windows alias uses host-format binary"
    else
      echo "warning: windows CLI alias unavailable"
    fi
  fi
else
  build_binary stonehenge-wiki-windows
  if copy_release_binary stonehenge-wiki-windows "" stonehenge-wiki-windows.exe; then
    echo "warning: windows target cross-build unavailable; windows alias uses host-format binary"
    echo "install rustup target add $WINDOWS_TARGET for native Windows packaging"
  else
    echo "warning: windows CLI alias unavailable"
  fi
fi

echo "[4/4] build validation"
for file in stonehenge-wiki stonehenge-wiki-linux stonehenge-wiki-windows.exe; do
  if [[ -f "$BIN_DIR/$file" ]]; then
    echo "  ✔ $file"
  else
    echo "  ⚠ $file (not available)"
  fi
done

echo "built binaries in $BIN_DIR"
