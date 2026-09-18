#!/usr/bin/env bash
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

CONFIG="${CONFIG:-udb-64-max}"
BUILD_TYPE="${BUILD_TYPE:-debug}"
IGNOREUNDEFINED="${IGNOREUNDEFINED:-YES}"
JOBS="${JOBS:-4}"
EXTENSIONS="${EXTENSIONS:-Vx8,Vx16,Vx32,Vx64,Vls8,Vls16,Vls32,Vls64,Vf16,Vf32,Vf64}"

RISCV_ARCH_TEST_REPO="${RISCV_ARCH_TEST_REPO:-https://github.com/riscv-non-isa/riscv-arch-test.git}"
RISCV_ARCH_TEST_REF="${RISCV_ARCH_TEST_REF:-edfa48d307ecda3d83b033dcb80ef96cde866994}"
RISCV_ARCH_TEST_DIR="${RISCV_ARCH_TEST_DIR:-${ROOT}/ext/riscv-arch-test}"
WORKDIR="${WORKDIR:-${RISCV_ARCH_TEST_DIR}/work/udb-64-max-vector}"

case "${BUILD_TYPE,,}" in
  debug)
    BUILD_DIR_TYPE="Debug"
    ;;
  release)
    BUILD_DIR_TYPE="Release"
    ;;
  *)
    echo "Unsupported BUILD_TYPE=${BUILD_TYPE}; expected debug or release." >&2
    exit 2
    ;;
esac

if [ "$CONFIG" != "udb-64-max" ]; then
  echo "This runner currently supports CONFIG=udb-64-max only." >&2
  exit 2
fi

if [ ! -e "${RISCV_ARCH_TEST_DIR}" ]; then
  mkdir -p "$(dirname "${RISCV_ARCH_TEST_DIR}")"
  git clone "${RISCV_ARCH_TEST_REPO}" "${RISCV_ARCH_TEST_DIR}"
  git -C "${RISCV_ARCH_TEST_DIR}" checkout "${RISCV_ARCH_TEST_REF}"
elif [ ! -d "${RISCV_ARCH_TEST_DIR}/.git" ]; then
  echo "${RISCV_ARCH_TEST_DIR} exists but is not a Git checkout." >&2
  exit 2
fi

git -C "${RISCV_ARCH_TEST_DIR}" fetch --quiet origin "${RISCV_ARCH_TEST_REF}"
git -C "${RISCV_ARCH_TEST_DIR}" checkout --detach --quiet "${RISCV_ARCH_TEST_REF}"

echo "Using riscv-arch-test at $(git -C "${RISCV_ARCH_TEST_DIR}" rev-parse --short HEAD)"

REPO_CONFIG_DIR="${ROOT}/cfgs/arch-test/udb-64-max"
CONFIG_FILE="${REPO_CONFIG_DIR}/test_config.yaml"
ISS="${ROOT}/gen/cpp_hart_gen/udb-64-max_${BUILD_DIR_TYPE}/build/iss"

if [ ! -f "${CONFIG_FILE}" ]; then
  echo "Missing repository test config ${CONFIG_FILE}." >&2
  exit 2
fi

"${ROOT}/do" build:iss "CONFIG=${CONFIG}" "BUILD_TYPE=${BUILD_TYPE}" \
  "IGNOREUNDEFINED=${IGNOREUNDEFINED}" "JOBS=${JOBS}"

make -C "${RISCV_ARCH_TEST_DIR}" elfs \
  "CONFIG_FILES=${CONFIG_FILE}" \
  "WORKDIR=${WORKDIR}" \
  "EXTENSIONS=${EXTENSIONS}" \
  "JOBS=${JOBS}"

"${RISCV_ARCH_TEST_DIR}/run_tests.py" --debug --jobs "${JOBS}" \
  "${ISS} -m udb-64-max -c ${ROOT}/cfgs/udb-64-max.yaml --uart-base 0x10000000 --clint-base 0x02000000" \
  "${WORKDIR}/udb-64-max/elfs"
