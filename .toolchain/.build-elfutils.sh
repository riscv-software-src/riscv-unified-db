#!/bin/bash

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Build elfutils libelf (configure + make + install). When
# UDB_TOOLCHAIN_CONTAINER=1 the entire sequence runs inside a single container
# invocation so that the hundreds of small autotools probe compilations don't
# each spawn their own container (as the per-call pattern in bin/g++ would).
#
# Called by CMake's ExternalProject_Add — do not invoke directly.
# Usage: .build-elfutils.sh <SOURCE_DIR> <BINARY_DIR> <INSTALL_DIR>

set -e

SOURCE_DIR=$1
BINARY_DIR=$2
INSTALL_DIR=$3

ROOT=$(dirname "$(realpath "${BASH_SOURCE[0]}")")
[ -f "${ROOT}/../.toolchain-local" ] && source "${ROOT}/../.toolchain-local"

if [ "${UDB_TOOLCHAIN_CONTAINER:-0}" = "1" ]; then
  # shellcheck source=../bin/.toolchain.sh
  source "${ROOT}/../bin/.toolchain.sh"
  cd "$BINARY_DIR"
  _setup_toolchain_run
  exec "${TOOLCHAIN_RUN[@]}" bash -c '
    set -e
    cd "$1"
    "$2/configure" \
      --prefix="$3" \
      --disable-shared \
      --enable-static \
      --disable-nls \
      --disable-debuginfod \
      --disable-libdebuginfod \
      --without-zstd \
      --without-bzlib \
      --without-lzma
    make -s -C lib
    make -s -C libelf
    make -s -C libelf install
  ' -- "$BINARY_DIR" "$SOURCE_DIR" "$INSTALL_DIR"
else
  cd "$BINARY_DIR"
  "$SOURCE_DIR/configure" \
    --prefix="$INSTALL_DIR" \
    --disable-shared \
    --enable-static \
    --disable-nls \
    --disable-debuginfod \
    --disable-libdebuginfod \
    --without-zstd \
    --without-bzlib \
    --without-lzma
  make -s -C lib
  make -s -C libelf
  make -s -C libelf install
fi
