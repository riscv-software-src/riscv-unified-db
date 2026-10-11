#!/bin/bash
# Shared helper for toolchain container wrappers.
# Source this file; do not execute it directly.
# Usage: source "$(dirname "$(realpath "${BASH_SOURCE[0]}")")/.toolchain.sh"

# Compute repo root from the location of this file (bin/.toolchain.sh → repo root)
_TOOLCHAIN_SCRIPT_DIR=$(dirname "$(realpath "${BASH_SOURCE[0]}")")
ROOT=$(dirname "${_TOOLCHAIN_SCRIPT_DIR}")

# Detect container runtime: prefer docker, fall back to podman, respect DOCKER/PODMAN env vars.
# Searches PATH and common absolute locations so this works even when PATH is restricted.
_get_toolchain_runtime() {
  local _docker _podman
  _docker="${DOCKER:-$(PATH="$PATH:/usr/bin:/usr/local/bin" command -v docker 2>/dev/null)}"
  _podman="${PODMAN:-$(PATH="$PATH:/usr/bin:/usr/local/bin" command -v podman 2>/dev/null)}"
  if [ -n "$_docker" ] && [ -x "$_docker" ]; then
    echo "$_docker"
  elif [ -n "$_podman" ] && [ -x "$_podman" ]; then
    echo "$_podman"
  else
    echo ""
  fi
}

# Compute toolchain container image tag as first 16 chars of SHA256 of .toolchain/Dockerfile
_TOOLCHAIN_HASH=$(sha256sum "${ROOT}/.toolchain/Dockerfile" | cut -c1-16)
TOOLCHAIN_IMAGE="ghcr.io/riscv/udb-toolchain:${_TOOLCHAIN_HASH}"

# Set up TOOLCHAIN_RUN for container invocations.
# Only called when UDB_TOOLCHAIN_CONTAINER=1.
_setup_toolchain_run() {
  local runtime
  runtime=$(_get_toolchain_runtime)
  if [ -z "$runtime" ]; then
    echo "ERROR: Neither docker nor podman found. Install one to use UDB_TOOLCHAIN_CONTAINER=1." >&2
    exit 1
  fi

  # Check if image exists locally; if not, try to pull
  if ! $runtime images --format "{{.Repository}}:{{.Tag}}" 2>/dev/null | grep -qF "${TOOLCHAIN_IMAGE}"; then
    echo "Toolchain image ${TOOLCHAIN_IMAGE} not found locally. Attempting to pull..." >&2
    if ! $runtime pull "${TOOLCHAIN_IMAGE}" 2>/dev/null; then
      echo "ERROR: Could not pull toolchain image ${TOOLCHAIN_IMAGE}." >&2
      echo "  To build it locally: docker build -t ${TOOLCHAIN_IMAGE} ${ROOT}/.toolchain/" >&2
      echo "  Or set UDB_TOOLCHAIN_CONTAINER=0 and install the toolchain natively." >&2
      exit 1
    fi
  fi

  local selinux_label=""
  if [[ "$runtime" == *podman* ]]; then
    selinux_label=":z"
  fi

  TOOLCHAIN_RUN=("$runtime" "run" "--rm")
  if [ -t 1 ] && [ -t 0 ]; then
    TOOLCHAIN_RUN+=("-it")
  fi
  TOOLCHAIN_RUN+=("-v" "${ROOT}:${ROOT}${selinux_label}")

  if [[ "$runtime" == *podman* ]]; then
    TOOLCHAIN_RUN+=("--userns=keep-id")
  else
    # For docker: copy /etc/passwd and /etc/group for user resolution (same pattern as bin/setup)
    mkdir -p "${ROOT}/.cache"
    getent passwd > "${ROOT}/.cache/passwd"
    getent group > "${ROOT}/.cache/group"
    TOOLCHAIN_RUN+=("--user" "$(id -u):$(id -g)"
                    "-v" "${ROOT}/.cache/passwd:/etc/passwd:ro"
                    "-v" "${ROOT}/.cache/group:/etc/group:ro")
  fi

  # Handle git worktrees: if .git is a file (worktree), also mount the parent git dir
  if [ -f "${ROOT}/.git" ]; then
    local git_common_dir
    git_common_dir=$(git -C "${ROOT}" rev-parse --git-common-dir | xargs dirname)
    TOOLCHAIN_RUN+=("-v" "${git_common_dir}:${git_common_dir}${selinux_label}")
  fi

  local host_pwd container_workdir
  host_pwd=$(realpath "${PWD}" 2>/dev/null || printf '%s\n' "${PWD}")
  container_workdir="${ROOT}"
  case "${host_pwd}" in
    "${ROOT}"|"${ROOT}"/*)
      container_workdir="${host_pwd}"
      ;;
  esac

  TOOLCHAIN_RUN+=("-w" "${container_workdir}" "${TOOLCHAIN_IMAGE}")
}

# Prompt the user to pick a toolchain when they previously selected "neither".
# Writes the new choice to .toolchain-local. Call this only when UDB_TOOLCHAIN_NONE=1.
_prompt_toolchain_selection() {
  if [ ! -t 0 ]; then
    echo "ERROR: Toolchain is required but not configured (UDB_TOOLCHAIN_NONE=1)." >&2
    echo "  Run bin/setup in an interactive terminal to choose a toolchain." >&2
    exit 1
  fi

  printf "\n  This command requires the C++ toolchain.\n"
  printf "  You previously opted out; please choose now:\n\n"
  printf "  [1] Container (recommended)\n"
  printf "      Docker/Podman pulls a pre-built image (~500 MB) from GHCR.\n\n"
  printf "  [2] Native\n"
  printf "      Requires GCC 13.3+ with C++23 support and a RISC-V cross-toolchain.\n\n"

  local _choice
  while true; do
    printf "  Enter 1 or 2 (default: 1): "
    read -r _choice
    _choice="${_choice:-1}"
    case "$_choice" in
      1) UDB_TOOLCHAIN_CONTAINER=1; break ;;
      2) UDB_TOOLCHAIN_CONTAINER=0; break ;;
      *) printf "  Please enter 1 or 2.\n" ;;
    esac
  done

  printf "UDB_TOOLCHAIN_CONTAINER=%s\n" "$UDB_TOOLCHAIN_CONTAINER" > "${ROOT}/.toolchain-local"
  printf "  Saved to .toolchain-local. Run bin/setup to change this later.\n\n"
}

# Pull or build the toolchain container image.
# In a GitHub Actions environment (GITHUB_ACTIONS=true), uses docker buildx with
# GHA layer caching.  Locally, falls back to a plain build.
# Only called when UDB_TOOLCHAIN_CONTAINER=1.
_pull_or_build_toolchain_image() {
  local runtime
  runtime=$(_get_toolchain_runtime)

  if [ -z "$runtime" ]; then
    return 1  # caller handles the "no runtime" message
  fi

  if $runtime images --format "{{.Repository}}:{{.Tag}}" 2>/dev/null | grep -qF "${TOOLCHAIN_IMAGE}"; then
    return 0  # already present
  fi

  if $runtime pull "${TOOLCHAIN_IMAGE}" 2>/dev/null; then
    return 0
  fi

  # Pull failed — build locally.
  if [ "${GITHUB_ACTIONS:-false}" = "true" ]; then
    # Use buildx with GHA layer cache when running in CI.
    $runtime buildx build \
      --cache-from type=gha,scope=toolchain \
      --cache-to   type=gha,scope=toolchain,mode=max \
      --load \
      -t "${TOOLCHAIN_IMAGE}" \
      -f "${ROOT}/.toolchain/Dockerfile" \
      "${ROOT}/.toolchain/"
  else
    $runtime build \
      -t "${TOOLCHAIN_IMAGE}" \
      -f "${ROOT}/.toolchain/Dockerfile" \
      "${ROOT}/.toolchain/"
  fi
}

# Check that the native g++ meets the project's C++ requirements by running the
# shared cmake check in .toolchain/check_cxx.cmake.
# Results are cached by compiler version string to avoid re-running on every invocation.
# Call this only on the native (non-container) path, with bin/ already stripped from PATH.
_check_native_cxx() {
  local version_str cache_key cache_file
  version_str=$(g++ --version 2>/dev/null) || {
    echo "ERROR: g++ not found or not executable." >&2
    exit 1
  }
  cache_key=$(printf '%s' "${version_str}" | sha256sum | cut -c1-16)
  cache_file="${ROOT}/.cache/cxx-check-${cache_key}"

  if [ -f "${cache_file}" ] && [ "$(cat "${cache_file}")" = "ok" ]; then
    return 0
  fi

  # Write a minimal CMakeLists.txt that delegates to the shared check file.
  local check_dir="${TMPDIR:-/tmp}/udb-cxx-check-$$"
  mkdir -p "${check_dir}"
  cat > "${check_dir}/CMakeLists.txt" <<EOF
cmake_minimum_required(VERSION 3.12)
project(cxx_check CXX)
include("${ROOT}/.toolchain/check_cxx.cmake")
EOF

  local cmake_ok=0
  if ${ROOT}/bin/cmake -S "${check_dir}" -B "${check_dir}/build" \
       --log-level=ERROR -Wno-dev > /dev/null 2>&1; then
    cmake_ok=1
  fi
  rm -rf "${check_dir}"

  if [ "${cmake_ok}" = "1" ]; then
    mkdir -p "${ROOT}/.cache"
    printf 'ok' > "${cache_file}"
  else
    echo "ERROR: Native g++ does not meet the project's C++ requirements." >&2
    echo "  See .toolchain/check_cxx.cmake for details." >&2
    echo "  Detected compiler: $(g++ --version | head -1)" >&2
    echo "  Option 1: Install a newer C++ compiler (GCC 14+)" >&2
    echo "  Option 2: Set UDB_TOOLCHAIN_CONTAINER=1 to use the toolchain container" >&2
    exit 1
  fi
}
