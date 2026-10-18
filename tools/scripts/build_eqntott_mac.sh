#!/usr/bin/env bash
# Copyright (c) 2026 Drona Gyawali
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Build eqntott from source natively on macOS.
# Produces a native Mach-O binary.
#
# Usage: build_eqntott_mac.sh [output_dir] [architecture]
#   output_dir   - where to place the binary (default: ./eqntott-build)
#   architecture - x64 or arm64 (default: native)
#
# EQNTOTT_VERSION in the udb gem is the single source of truth.
# To update: change tools/ruby-gems/udb/lib/udb/EQNTOTT_VERSION.

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
EQNTOTT_VERSION_FILE="${UDB_ROOT}/tools/ruby-gems/udb/lib/udb/EQNTOTT_VERSION"
EQNTOTT_VERSION=$(<"${EQNTOTT_VERSION_FILE}") || error "Could not read ${EQNTOTT_VERSION_FILE}"

case "${EQNTOTT_VERSION}" in
  eqntott-*)
    EQNTOTT_COMMIT="${EQNTOTT_VERSION#eqntott-}"
    ;;
  *)
    error "Invalid EQNTOTT_VERSION '${EQNTOTT_VERSION}'; expected eqntott-<git-commit>"
    ;;
esac

if [[ ! "${EQNTOTT_COMMIT}" =~ ^[a-f0-9]{7,40}$ ]]; then
  error "Invalid EQNTOTT_VERSION '${EQNTOTT_VERSION}'; expected eqntott-<7-to-40-char-hex-commit>"
fi

build_eqntott_mac() {
  local output_dir="${1:-./eqntott-build}"
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

  info "Building eqntott (${EQNTOTT_VERSION}, commit ${EQNTOTT_COMMIT})"
  info "Output directory: $output_dir"
  info "Architecture: $architecture"

  # Check required tools
  command_exists git      || error "git is not installed"
  command_exists make     || error "make is not installed (install Xcode Command Line Tools)"
  command_exists autoconf || error "autoconf is not installed (run: brew install autoconf)"
  command_exists automake || error "automake is not installed (run: brew install automake)"

  local temp_dir
  temp_dir=$(mktemp -d -t eqntott-build-XXXXXX)
  trap "rm -rf '$temp_dir'" EXIT

  info "Using temporary directory: $temp_dir"

  # Clone and checkout
  info "Cloning eqntott source..."
  git clone https://github.com/TheProjecter/eqntott.git "$temp_dir/eqntott"
  cd "$temp_dir/eqntott"
  git checkout "${EQNTOTT_COMMIT}"

  # Configure and build natively for target arch with legacy C tolerance
  info "Configuring..."
  local legacy_cflags="${arch_flag} -Wno-implicit-int -Wno-implicit-function-declaration -Wno-return-mismatch -Wno-incompatible-function-pointer-types -Wno-deprecated-non-prototype -std=gnu89"

  ./configure CC="clang" CFLAGS="${legacy_cflags}" LDFLAGS="${arch_flag}"

  info "Building..."
  make -j"$(sysctl -n hw.logicalcpu)"

  strip "$temp_dir/eqntott/src/eqntott" 2>/dev/null || true

  mkdir -p "$output_dir"
  cp "$temp_dir/eqntott/src/eqntott" "$output_dir/eqntott"
  chmod +x "$output_dir/eqntott"

  # Verify it is a Mach-O binary
  if ! file "$output_dir/eqntott" | grep -q "Mach-O"; then
    error "Built binary is not a Mach-O file: $(file "$output_dir/eqntott")"
  fi

  info "Build completed successfully!"
  info "Binary: $output_dir/eqntott"
  file "$output_dir/eqntott"
  ls -lh "$output_dir/eqntott"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ $# -gt 0 ]] && [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: $0 [output_dir] [architecture]" >&2
    echo "  output_dir   - where to place the binary (default: ./eqntott-build)" >&2
    echo "  architecture - x64 or arm64 (default: native)" >&2
    exit 0
  fi
  build_eqntott_mac "${1:-./eqntott-build}" "${2:-$(uname -m)}"
fi
