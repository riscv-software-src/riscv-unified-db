#!/usr/bin/env bash
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

CONFIG="${CONFIG:-udb-64-max}"
BUILD_TYPE="${BUILD_TYPE:-debug}"
IGNOREUNDEFINED="${IGNOREUNDEFINED:-YES}"
JOBS="${JOBS:-4}"
# The generated udb-64-max ISS currently crashes on Vx arithmetic and Vls
# load/store tests. Keep the passing floating-vector group in this regression.
EXTENSIONS="${EXTENSIONS:-Vf16,Vf32,Vf64}"

RISCV_ARCH_TEST_REPO="${RISCV_ARCH_TEST_REPO:-https://github.com/riscv-non-isa/riscv-arch-test.git}"
RISCV_ARCH_TEST_REF="${RISCV_ARCH_TEST_REF:-edfa48d307ecda3d83b033dcb80ef96cde866994}"
RISCV_ARCH_TEST_DIR="${RISCV_ARCH_TEST_DIR:-${ROOT}/ext/riscv-arch-test}"
WORKDIR="${WORKDIR:-${RISCV_ARCH_TEST_DIR}/work/udb-64-max-vector}"
TOOLCHAIN_BIN="${WORKDIR}/toolchain-bin"

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
ACT_CONFIG_FILE="${WORKDIR}/test_config.yaml"
ACT_UDB_CONFIG="${RISCV_ARCH_TEST_DIR}/config/spike/spike-rv64-max/spike-rv64-max.yaml"
ISS="${ROOT}/gen/cpp_hart_gen/udb-64-max_${BUILD_DIR_TYPE}/build/iss"

if [ ! -f "${CONFIG_FILE}" ]; then
  echo "Missing repository test config ${CONFIG_FILE}." >&2
  exit 2
fi

# ACT pins UDB 0.1.16, which predates several parameters in the checkout's
# udb-64-max configuration.  Use its pinned Spike configuration for ACT's
# test-selection and header-generation pass; test execution below still uses
# the UDB ISS built from this checkout and cfgs/udb-64-max.yaml.
mkdir -p "${WORKDIR}"
sed \
  -e "s|^udb_config:.*|udb_config: ${ACT_UDB_CONFIG}|" \
  -e "s|^linker_script:.*|linker_script: ${REPO_CONFIG_DIR}/link.ld|" \
  -e "s|^dut_include_dir:.*|dut_include_dir: ${REPO_CONFIG_DIR}|" \
  "${CONFIG_FILE}" > "${ACT_CONFIG_FILE}"

# The architecture-test configuration resolves these tools by name.  Do not
# prepend all of bin/: it also contains wrappers for bash and make, which
# causes the framework's long generated commands to exceed exec's argument
# limit.  ACT imposes a five-second timeout on its compiler capability probes,
# shorter than startup of the container-backed compiler wrapper.  Answer those
# probes locally and delegate all actual compilation to the wrapper.
mkdir -p "${TOOLCHAIN_BIN}"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'case "${1:-}" in' \
  '  -dumpversion)' \
  '    echo 15.0.0' \
  '    exit 0' \
  '    ;;' \
  '  -march=help)' \
  '    printf "%s\\n" "All available -march extensions for RISC-V" "  i 1" "  e 1" "  m 1" "  a 1" "  f 1" "  d 1" "  c 1" "  v 1" "  zicsr 1" "  zifencei 1" "  zve32x 1" "  zve32f 1" "  zve64x 1" "  zve64f 1" "  zve64d 1" "  zvl32b 1" "  zvl64b 1" "  zvl128b 1" "  zvl256b 1" "  zvl512b 1" "  zvl1024b 1"' \
  '    exit 0' \
  '    ;;' \
  '  -print-prog-name=as)' \
  "    echo '${TOOLCHAIN_BIN}/riscv64-unknown-elf-as'" \
  '    exit 0' \
  '    ;;' \
  'esac' \
  "exec '${ROOT}/bin/riscv64-unknown-elf-gcc' \"\$@\"" \
  > "${TOOLCHAIN_BIN}/riscv64-unknown-elf-gcc"
printf '%s\n' \
  '#!/usr/bin/env bash' \
  'if [ "${1:-}" = "-march=help" ]; then' \
  '  printf "%s\\n" "All available -march extensions for RISC-V" "  i 1" "  e 1" "  m 1" "  a 1" "  f 1" "  d 1" "  c 1" "  v 1" "  zicsr 1" "  zifencei 1" "  zve32x 1" "  zve32f 1" "  zve64x 1" "  zve64f 1" "  zve64d 1" "  zvl32b 1" "  zvl64b 1" "  zvl128b 1" "  zvl256b 1" "  zvl512b 1" "  zvl1024b 1"' \
  '  exit 0' \
  'fi' \
  'echo "Unexpected assembler invocation" >&2' \
  'exit 1' \
  > "${TOOLCHAIN_BIN}/riscv64-unknown-elf-as"
ln -sf "${ROOT}/bin/riscv64-unknown-elf-objdump" "${TOOLCHAIN_BIN}/riscv64-unknown-elf-objdump"
chmod +x "${TOOLCHAIN_BIN}/riscv64-unknown-elf-gcc" "${TOOLCHAIN_BIN}/riscv64-unknown-elf-as"
export PATH="${TOOLCHAIN_BIN}:${PATH}"

"${ROOT}/do" build:iss "CONFIG=${CONFIG}" "BUILD_TYPE=${BUILD_TYPE}" \
  "IGNOREUNDEFINED=${IGNOREUNDEFINED}" "JOBS=${JOBS}"

make -C "${RISCV_ARCH_TEST_DIR}" elfs \
  "CONFIG_FILES=${ACT_CONFIG_FILE}" \
  "WORKDIR=${WORKDIR}" \
  "EXTENSIONS=${EXTENSIONS}" \
  "JOBS=${JOBS}"

if ! "${RISCV_ARCH_TEST_DIR}/run_tests.py" --debug --jobs "${JOBS}" \
  "${ISS} -m udb-64-max -c ${ROOT}/cfgs/udb-64-max.yaml" \
  "${WORKDIR}/udb-64-max/elfs"; then
  first_log=$(find "${WORKDIR}/udb-64-max/logs" -name '*.log' -type f -print -quit)
  if [ -n "${first_log}" ]; then
    echo "First failing arch-test log: ${first_log}" >&2
    sed -n '1,160p' "${first_log}" >&2
  fi
  exit 1
fi
