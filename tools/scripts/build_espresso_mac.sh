#!/usr/bin/env bash
# Copyright (c) 2026 Drona Gyawali
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Build espresso from source natively on macOS.
# Produces a native Mach-O binary.
#
# Usage: build_espresso_mac.sh [output_dir] [architecture]
#   output_dir   - where to place the binary (default: ./espresso-build)
#   architecture - x64 or arm64 (default: native)
#
# ESPRESSO_VERSION in the udb gem is the single source of truth.
# To update: change tools/ruby-gems/udb/lib/udb/ESPRESSO_VERSION.

set -euo pipefail

error() { echo "ERROR: $*" >&2; exit 1; }
info()  { echo "INFO: $*"  >&2; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

# Must run on macOS
if [[ "$(uname -s)" != "Darwin" ]]; then
  error "This script must be run on macOS"
fi

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
UDB_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)
ESPRESSO_VERSION_FILE="${UDB_ROOT}/tools/ruby-gems/udb/lib/udb/ESPRESSO_VERSION"
ESPRESSO_VERSION=$(<"${ESPRESSO_VERSION_FILE}") || error "Could not read ${ESPRESSO_VERSION_FILE}"

case "${ESPRESSO_VERSION}" in
  espresso-*)
    ESPRESSO_COMMIT="${ESPRESSO_VERSION#espresso-}"
    ;;
  *)
    error "Invalid ESPRESSO_VERSION '${ESPRESSO_VERSION}'; expected espresso-<git-commit>"
    ;;
esac

if [[ ! "${ESPRESSO_COMMIT}" =~ ^[a-f0-9]{7,40}$ ]]; then
  error "Invalid ESPRESSO_VERSION '${ESPRESSO_VERSION}'; expected espresso-<7-to-40-char-hex-commit>"
fi

build_espresso_mac() {
  local output_dir="${1:-./espresso-build}"
  local raw_arch="${2:-$(uname -m)}"

  # Normalize architecture using POSIX tr (compatible with Bash 3.2+)
  local arch_lower
  arch_lower=$(echo "$raw_arch" | tr '[:upper:]' '[:lower:]')

  case "${arch_lower}" in
    x64|amd64|x86_64)
      architecture="x64"
      local arch_flag="-arch x86_64"
      ;;
    arm64|aarch64)
      architecture="arm64"
      local arch_flag="-arch arm64"
      ;;
    *)
      error "Invalid architecture: $raw_arch. Must be x64 or arm64"
      ;;
  esac

  info "Building espresso (${ESPRESSO_VERSION}, commit ${ESPRESSO_COMMIT})"
  info "Output directory: $output_dir"
  info "Architecture: $architecture"

  # Check required tools
  command_exists git      || error "git is not installed"
  command_exists make     || error "make is not installed (install Xcode Command Line Tools)"
  command_exists autoconf || error "autoconf is not installed (run: brew install autoconf)"
  command_exists automake || error "automake is not installed (run: brew install automake)"

  local temp_dir
  temp_dir=$(mktemp -d -t espresso-build-XXXXXX)
  trap "rm -rf '$temp_dir'" EXIT

  info "Using temporary directory: $temp_dir"

  # Clone and checkout
  info "Cloning espresso source..."
  git clone https://github.com/psksvp/espresso-ab-1.0.git "$temp_dir/espresso"
  cd "$temp_dir/espresso"
  git checkout "${ESPRESSO_COMMIT}"

  # Configure and build natively for target arch with legacy C tolerance
  info "Configuring..."
  local legacy_cflags="${arch_flag} -Wno-implicit-int -Wno-implicit-function-declaration -Wno-return-mismatch -Wno-incompatible-function-pointer-types -Wno-deprecated-non-prototype -std=gnu89"

  ./configure CC="clang" CFLAGS="${legacy_cflags}" LDFLAGS="${arch_flag}"

  info "Building..."
  make -j"$(sysctl -n hw.logicalcpu)"

  # Strip and copy binary
  strip "$temp_dir/espresso/src/espresso" 2>/dev/null || true

  mkdir -p "$output_dir"

  # espresso installs to /usr/local/bin after make install, but we grab from src
  if [ -f "$temp_dir/espresso/src/espresso" ]; then
    cp "$temp_dir/espresso/src/espresso" "$output_dir/espresso"
  else
    # fallback: run make install into a local prefix
    make install prefix="$temp_dir/espresso-install"
    cp "$temp_dir/espresso-install/bin/espresso" "$output_dir/espresso"
  fi

  chmod +x "$output_dir/espresso"

  # Verify it is a Mach-O binary
  if ! file "$output_dir/espresso" | grep -q "Mach-O"; then
    error "Built binary is not a Mach-O file: $(file "$output_dir/espresso")"
  fi

  info "Build completed successfully!"
  info "Binary: $output_dir/espresso"
  file "$output_dir/espresso"
  ls -lh "$output_dir/espresso"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ $# -gt 0 ]] && [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: $0 [output_dir] [architecture]" >&2
    echo "  output_dir   - where to place the binary (default: ./espresso-build)" >&2
    echo "  architecture - x64 or arm64 (default: native)" >&2
    exit 0
  fi
  build_espresso_mac "${1:-./espresso-build}" "${2:-$(uname -m)}"
fi
