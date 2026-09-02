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
RISCV_ARCH_TEST_REF="${RISCV_ARCH_TEST_REF:-ba53eb88ad021dd69419cacfcfc9a3f8c104f988}"
RISCV_ARCH_TEST_DIR="${RISCV_ARCH_TEST_DIR:-${ROOT}/ext/riscv-arch-test}"

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

echo "Using riscv-arch-test at $(git -C "${RISCV_ARCH_TEST_DIR}" rev-parse --short HEAD)"

SOURCE_CONFIG_DIR="${RISCV_ARCH_TEST_DIR}/config/spike/spike-rv64-max"
TARGET_CONFIG_DIR="${RISCV_ARCH_TEST_DIR}/config/udb/udb-64-max"
ISS="${ROOT}/gen/cpp_hart_gen/udb-64-max_${BUILD_DIR_TYPE}/build/iss"
UDB_CONFIG="${TARGET_CONFIG_DIR}/udb-64-max.yaml"

if [ ! -d "${SOURCE_CONFIG_DIR}" ]; then
  echo "Missing ${SOURCE_CONFIG_DIR}; selected riscv-arch-test checkout is not compatible." >&2
  exit 2
fi

rm -rf "${TARGET_CONFIG_DIR}"
mkdir -p "$(dirname "${TARGET_CONFIG_DIR}")"
cp -a "${SOURCE_CONFIG_DIR}" "${TARGET_CONFIG_DIR}"
rm -f "${TARGET_CONFIG_DIR}/spike-rv64-max.yaml"
cp "${ROOT}/cfgs/udb-64-max.yaml" "${UDB_CONFIG}"

perl -0pi -e 's/name: spike-rv64-max/name: udb-64-max/' "${TARGET_CONFIG_DIR}/test_config.yaml"
perl -0pi -e 's/udb_config: spike-rv64-max\.yaml/udb_config: udb-64-max.yaml/' "${TARGET_CONFIG_DIR}/test_config.yaml"

perl -0pi -e 's/"writable_fiom": false/"writable_fiom": true/' "${TARGET_CONFIG_DIR}/sail.json"
perl -0pi -e 's/"count": 64/"count": 0/' "${TARGET_CONFIG_DIR}/sail.json"
perl -0pi -e 's/"usable_count": 64/"usable_count": 0/' "${TARGET_CONFIG_DIR}/sail.json"
perl -0pi -e 's/"arith": true/"arith": false/' "${TARGET_CONFIG_DIR}/sail.json"
perl -0pi -e 's/"supported": false/"supported": true/' "${TARGET_CONFIG_DIR}/sail.json"

cat > "${TARGET_CONFIG_DIR}/run_cmd.txt" <<EOF
${ISS} -m udb-64-max -c ${UDB_CONFIG} --uart-base 0x10000000 --clint-base 0x02000000
EOF

cat > "${TARGET_CONFIG_DIR}/rvmodel_macros.h" <<'EOF'
// rvmodel_macros.h for UDB ISS.
// Uses standard HTIF tohost/fromhost termination via 64-bit writes.

#ifndef RVMODEL_MACROS_H
#define RVMODEL_MACROS_H

#define RVMODEL_DATA_SECTION \
    .pushsection .tohost,"aw",@progbits; \
    .balign 8; .global tohost; tohost: .dword 0; \
    .balign 8; .global fromhost; fromhost: .dword 0; \
    .popsection;

#define STANDARD_SM_SUPPORTED
#undef SMRNMI_SUPPORTED

#define UDB_ZAWRS_NTO_IS_NOP
#define RVMODEL_ACCESS_FAULT_ADDRESS 0x00000000

#define RVMODEL_HALT_PASS \
    li   t0, 1;                           \
    la   t1, tohost;                      \
    sd   t0, 0(t1);                       \
    1: j 1b;                              \

#define RVMODEL_HALT_FAIL \
    li   t0, 3;                           \
    la   t1, tohost;                      \
    sd   t0, 0(t1);                       \
    1: j 1b;                              \

#define RVMODEL_IO_INIT(_R1, _R2, _R3)
#define RVMODEL_IO_WRITE_STR(_R1, _R2, _R3, _STR_PTR) \
1:                           ;                        \
  lbu  _R1, 0(_STR_PTR)      ;                        \
  beqz _R1, 3f               ;                        \
2:                           ;                        \
  li   _R2, 0x10000005       ;                        \
  lbu  _R3, 0(_R2)           ;                        \
  andi _R3, _R3, 0x20        ;                        \
  beqz _R3, 2b               ;                        \
  li   _R2, 0x10000000       ;                        \
  sb   _R1, 0(_R2)           ;                        \
  addi _STR_PTR, _STR_PTR, 1 ;                        \
  j 1b                       ;                        \
3:
#define RVMODEL_DATA_BEGIN
#define RVMODEL_DATA_END

#define RVMODEL_INTERRUPT_LATENCY  10
#define RVMODEL_TIMER_INT_SOON_DELAY  100
#define RVMODEL_MTIME_ADDRESS  0x0200BFF8
#define RVMODEL_MTIMECMP_ADDRESS  0x02004000
#define RVMODEL_MSIP_ADDRESS  0x02000000
#define RVMODEL_TEST_INTERRUPT_ADDRESS 0x0c000004
#define RVMODEL_SET_MEXT_INT(_R1, _R2) \
    li _R1, (1 << 31) | (1 << 11); \
    li _R2, RVMODEL_TEST_INTERRUPT_ADDRESS; \
    sw _R1, 0(_R2)
#define RVMODEL_CLR_MEXT_INT(_R1, _R2) \
    li _R1, (1 << 11); \
    li _R2, RVMODEL_TEST_INTERRUPT_ADDRESS; \
    sw _R1, 0(_R2)
#define RVMODEL_SET_MSW_INT(_R1, _R2) \
    li _R1, 1; \
    li _R2, RVMODEL_MSIP_ADDRESS; \
    sw _R1, 0(_R2)
#define RVMODEL_CLR_MSW_INT(_R1, _R2) \
    li _R2, RVMODEL_MSIP_ADDRESS; \
    sw zero, 0(_R2)
#define RVMODEL_SET_SEXT_INT(_R1, _R2) \
    li _R1, (1 << 31) | (1 << 9); \
    li _R2, RVMODEL_TEST_INTERRUPT_ADDRESS; \
    sw _R1, 0(_R2)
#define RVMODEL_CLR_SEXT_INT(_R1, _R2) \
    li _R1, (1 << 9); \
    li _R2, RVMODEL_TEST_INTERRUPT_ADDRESS; \
    sw _R1, 0(_R2)
#define RVMODEL_SET_SSW_INT(_R1, _R2) \
    li _R1, (1 << 31) | (1 << 1); \
    li _R2, RVMODEL_TEST_INTERRUPT_ADDRESS; \
    sw _R1, 0(_R2)
#define RVMODEL_CLR_SSW_INT(_R1, _R2) \
    li _R1, (1 << 1); \
    li _R2, RVMODEL_TEST_INTERRUPT_ADDRESS; \
    sw _R1, 0(_R2)

#endif // RVMODEL_MACROS_H
EOF

"${ROOT}/do" build:iss "CONFIG=${CONFIG}" "BUILD_TYPE=${BUILD_TYPE}" \
  "IGNOREUNDEFINED=${IGNOREUNDEFINED}" "JOBS=${JOBS}"

make -C "${RISCV_ARCH_TEST_DIR}" udb-64-max \
  "EXTENSIONS=${EXTENSIONS}" \
  "JOBS=${JOBS}"
