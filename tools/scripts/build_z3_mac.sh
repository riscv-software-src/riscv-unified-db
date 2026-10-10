#!/usr/bin/env bash
# Copyright (c) 2026 Drona Gyawali
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Build Z3 from source natively on macOS.
# Produces a native Mach-O .dylib.
#
# Usage: build_z3_mac.sh [output_dir] [build_type] [architecture]
#   output_dir   - where to extract Z3 installation (default: ./z3-build)
#   build_type   - Release, Debug, etc. (default: Release)
#   architecture - x64 or arm64 (default: native)
#
# Z3_VERSION in the udb gem is the single source of truth.
# To update: change tools/ruby-gems/udb/lib/udb/Z3_VERSION.

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
Z3_VERSION_FILE="${UDB_ROOT}/tools/ruby-gems/udb/lib/udb/Z3_VERSION"
Z3_VERSION=$(<"${Z3_VERSION_FILE}") || error "Could not read ${Z3_VERSION_FILE}"

if [[ ! "${Z3_VERSION}" =~ ^z3-[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  error "Invalid Z3_VERSION '${Z3_VERSION}'; expected z3-<major>.<minor>.<patch>"
fi

build_z3_mac() {
  local output_dir="${1:-./z3-build}"
  local build_type="${2:-Release}"
  local raw_arch="${3:-$(uname -m)}"

  # Validate build type
  if [[ ! "$build_type" =~ ^(Release|Debug|RelWithDebInfo|MinSizeRel)$ ]]; then
    error "Invalid build type: $build_type. Must be Release, Debug, RelWithDebInfo, or MinSizeRel"
  fi

  # Normalize architecture using POSIX tr (compatible with macOS Bash 3.2)
  local arch_lower
  arch_lower=$(echo "$raw_arch" | tr '[:upper:]' '[:lower:]')

  case "${arch_lower}" in
    x64|amd64|x86_64)
      architecture="x64"
      local cmake_arch="x86_64"
      ;;
    arm64|aarch64)
      architecture="arm64"
      local cmake_arch="arm64"
      ;;
    *)
      error "Invalid architecture: $raw_arch. Must be x64 or arm64"
      ;;
  esac

  info "Building Z3 (${Z3_VERSION})"
  info "Output directory: $output_dir"
  info "Build type: $build_type"
  info "Architecture: $architecture (cmake: $cmake_arch)"

  # Check required tools
  command_exists git     || error "git is not installed"
  command_exists cmake   || error "cmake is not installed (run: brew install cmake)"
  command_exists python3 || error "python3 is not installed"

  local temp_dir
  temp_dir=$(mktemp -d -t z3-build-XXXXXX)
  trap "rm -rf '$temp_dir'" EXIT

  info "Using temporary directory: $temp_dir"

  # Check for GitHub token (avoids rate limiting)
  local auth_header=""
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    auth_header="Authorization: Bearer $GITHUB_TOKEN"
    info "Using GitHub authentication token"
  fi

  # Download source tarball
  local tarball_url="https://github.com/Z3Prover/z3/archive/refs/tags/${Z3_VERSION}.tar.gz"
  local tarball_path="$temp_dir/z3.tar.gz"

  info "Downloading Z3 source from: $tarball_url"
  if [[ -n "$auth_header" ]]; then
    curl -L -H "$auth_header" -o "$tarball_path" "$tarball_url" || error "Failed to download Z3 source"
  else
    curl -L -o "$tarball_path" "$tarball_url" || error "Failed to download Z3 source"
  fi

  # Verify gzip
  if ! file "$tarball_path" | grep -q "gzip compressed"; then
    info "Downloaded file is not a gzip archive. First 500 bytes:"
    head -c 500 "$tarball_path" >&2
    error "Downloaded file is not in gzip format. Check that ${Z3_VERSION} is a valid Z3 tag."
  fi

  info "Extracting source tarball..."
  tar -xzf "$tarball_path" -C "$temp_dir" || error "Failed to extract tarball"

  local source_dir
  source_dir=$(find "$temp_dir" -maxdepth 1 -type d -name "z3-*" ! -path "$temp_dir" | head -n 1)
  [[ -z "$source_dir" ]] && error "Could not find extracted Z3 source directory"
  info "Source directory: $source_dir"

  # Configure with CMake targeting the right arch
  local install_dir="$temp_dir/z3-install"
  mkdir -p "$temp_dir/z3-cmake-build"
  cd "$temp_dir/z3-cmake-build"

  info "Configuring with CMake..."
  cmake "$source_dir" \
    -DCMAKE_BUILD_TYPE="${build_type}" \
    -DCMAKE_INSTALL_PREFIX="${install_dir}" \
    -DCMAKE_OSX_ARCHITECTURES="${cmake_arch}" \
    -DZ3_BUILD_LIBZ3_SHARED=ON \
    -DZ3_BUILD_EXECUTABLE=OFF \
    -DZ3_BUILD_TEST_EXECUTABLES=OFF

  info "Building..."
  cmake --build . --config "${build_type}" -j"$(sysctl -n hw.logicalcpu)"

  info "Installing..."
  cmake --install . --config "${build_type}"

  # Copy install tree to output_dir
  mkdir -p "$output_dir"
  cp -r "$install_dir/." "$output_dir/"

  # Write VERSION file (mirrors Docker script)
  echo "$Z3_VERSION" > "$output_dir/VERSION"

  # Verify the dylib is Mach-O
  local dylib="$output_dir/lib/libz3.dylib"
  if [[ ! -f "$dylib" ]]; then
    error "libz3.dylib not found at $dylib"
  fi
  if ! file "$dylib" | grep -q "Mach-O"; then
    error "Built library is not a Mach-O file: $(file "$dylib")"
  fi

  info "Build completed successfully!"
  info "Z3 version: $Z3_VERSION"
  info "Build type: $build_type"
  info "Installation directory: $(cd "$output_dir" && pwd)"
  info ""
  info "Libraries:"
  ls -lh "$output_dir/lib"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ $# -gt 0 ]] && [[ "$1" == "-h" || "$1" == "--help" || "$1" == "help" ]]; then
    echo "Usage: $0 [output_dir] [build_type] [architecture]" >&2
    echo "  output_dir   - Directory to extract Z3 installation (default: ./z3-build)" >&2
    echo "  build_type   - CMake build type: Release, Debug, RelWithDebInfo, or MinSizeRel (default: Release)" >&2
    echo "  architecture - Target architecture: x64 or arm64 (default: native)" >&2
    echo "" >&2
    echo "Examples:" >&2
    echo "  $0                              # Build native arch to ./z3-build" >&2
    echo "  $0 ./z3-arm64 Release arm64     # Build arm64 to ./z3-arm64" >&2
    echo "  $0 ./z3-x64   Release x64       # Build x64   to ./z3-x64" >&2
    exit 0
  fi
  build_z3_mac "${1:-./z3-build}" "${2:-Release}" "${3:-$(uname -m)}"
fi
