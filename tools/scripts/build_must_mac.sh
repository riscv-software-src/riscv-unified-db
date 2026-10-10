#!/usr/bin/env bash
# Copyright (c) 2026 Drona Gyawali
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Build must (mustool) from source natively on macOS.
# Produces a native Mach-O binary.
#
# Usage: build_must_mac.sh [output_dir] [architecture]
#   output_dir   - where to place the binary (default: ./must-build)
#   architecture - x64 or arm64 (default: native)
#
# MUST_VERSION in the udb gem is the single source of truth.
# To update: change tools/ruby-gems/udb/lib/udb/MUST_VERSION.

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
MUST_VERSION_FILE="${UDB_ROOT}/tools/ruby-gems/udb/lib/udb/MUST_VERSION"
MUST_VERSION=$(<"${MUST_VERSION_FILE}") || error "Could not read ${MUST_VERSION_FILE}"

case "${MUST_VERSION}" in
  must-*)
    MUST_COMMIT="${MUST_VERSION#must-}"
    ;;
  *)
    error "Invalid MUST_VERSION '${MUST_VERSION}'; expected must-<git-commit>"
    ;;
esac

if [[ ! "${MUST_COMMIT}" =~ ^[a-f0-9]{7,40}$ ]]; then
  error "Invalid MUST_VERSION '${MUST_VERSION}'; expected must-<7-to-40-char-hex-commit>"
fi

build_must_mac() {
  local output_dir="${1:-./must-build}"
  local raw_arch="${2:-$(uname -m)}"

  # Normalize architecture using POSIX tr (compatible with macOS Bash 3.2)
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

  info "Building must (${MUST_VERSION}, commit ${MUST_COMMIT})"
  info "Output directory: $output_dir"
  info "Architecture: $architecture"

  # Check required tools
  command_exists git  || error "git is not installed"
  command_exists make || error "make is not installed (install Xcode Command Line Tools)"

  local temp_dir
  temp_dir=$(mktemp -d -t must-build-XXXXXX)
  trap "rm -rf '$temp_dir'" EXIT

  info "Using temporary directory: $temp_dir"

  # Clone and checkout
  info "Cloning mustool source..."
  git clone https://github.com/jar-ben/mustool.git "$temp_dir/must"
  cd "$temp_dir/must"
  git checkout "${MUST_COMMIT}"

  # Apply the missing #include <cstdio> patch (same as Docker build)
  info "Applying patch..."

  # signal.h needs <cstdio>
  sed -i '' -e 's/#include <signal.h>/#include <signal.h>\n#include <cstdio>/' \
    mcsmus/mcsmus/control.cc

  # Replace PRI macros with literals (macOS does not like the PRI* macros in some contexts)
  find . -type f \( -name "*.h" -o -name "*.cc" -o -name "*.cpp" -o -name "*.hh" \) \
    -exec sed -i '' 's/PRIi64/"lld"/g; s/PRIu64/"llu"/g' {} +

  # Fix memUsedPeak signature mismatch (header has bool, .cc was missing it)
  sed -i '' \
    -e 's/double Minisat::memUsedPeak() { return memUsed(); }/double Minisat::memUsedPeak(bool) { return memUsed(); }/' \
    -e 's/double Minisat::memUsedPeak() { return 0; }/double Minisat::memUsedPeak(bool) { return 0; }/' \
    mcsmus/minisat/utils/System.cc

  # Remove obsolete -lstdc++fs (not needed on Apple Clang / libc++)
  grep -rl 'stdc++fs' . 2>/dev/null | xargs sed -i '' 's/-lstdc++fs//g' || true

  # Build natively for target arch
  info "Building..."
  make -j"$(sysctl -n hw.logicalcpu)" \
    CC="clang++" \
    CXXFLAGS="${arch_flag}" \
    LDFLAGS="${arch_flag}"

  strip "$temp_dir/must/must" 2>/dev/null || true

  mkdir -p "$output_dir"
  cp "$temp_dir/must/must" "$output_dir/must"
  chmod +x "$output_dir/must"

  # Verify it is a Mach-O binary
  if ! file "$output_dir/must" | grep -q "Mach-O"; then
    error "Built binary is not a Mach-O file: $(file "$output_dir/must")"
  fi

  info "Build completed successfully!"
  info "Binary: $output_dir/must"
  file "$output_dir/must"
  ls -lh "$output_dir/must"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ $# -gt 0 ]] && [[ "$1" == "-h" || "$1" == "--help" ]]; then
    echo "Usage: $0 [output_dir] [architecture]" >&2
    echo "  output_dir   - where to place the binary (default: ./must-build)" >&2
    echo "  architecture - x64 or arm64 (default: native)" >&2
    exit 0
  fi
  build_must_mac "${1:-./must-build}" "${2:-$(uname -m)}"
fi
