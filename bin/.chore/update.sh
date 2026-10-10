#!/bin/bash

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Update operations for bin/chore
# This file contains all update-related subcommands

#
# Update Ruby gems
# Returns: 0 on success, exits with 1 on error
#
do_update_gems() {
  # first, update Gemfile.lock files and sorbet definitions.
  # Delete all lockfiles first so --update resolves fresh, then re-lock root
  # before per-gem files so they are derived from the same resolved graph.
  rm "${UDB_ROOT}"/Gemfile.lock
  rm "${UDB_ROOT}"/tools/ruby-gems/idlc/Gemfile.lock
  rm "${UDB_ROOT}"/tools/ruby-gems/udb/Gemfile.lock
  rm "${UDB_ROOT}"/tools/ruby-gems/udb-gen/Gemfile.lock
  rm "${UDB_ROOT}"/tools/ruby-gems/udb_helpers/Gemfile.lock
  do_lock_all_gemfiles --update --bundler

  "${UDB_ROOT}"/bin/bundle exec bundle install
  do_ruby_type_def idlc
  do_ruby_type_def udb
  do_ruby_type_def udb-gen
}

# Read a git-pinned binary dependency version from its *_VERSION file.
# Args: $1 - tool/release prefix, e.g. "espresso"
#       $2 - version file path
#       $3 - output variable for the full version string
#       $4 - output variable for the git commit portion
read_git_pinned_tool_version() {
  local tool=$1
  local version_file=$2
  local version_var=$3
  local commit_var=$4
  local version
  local commit

  version=$(<"${version_file}") || {
    echo "ERROR: Could not read ${version_file}" >&2
    exit 1
  }

  if [[ "${version}" != "${tool}-"* ]]; then
    echo "ERROR: Invalid ${version_file}: expected ${tool}-<git-commit>, got '${version}'" >&2
    exit 1
  fi

  commit="${version#${tool}-}"
  if [[ ! "${commit}" =~ ^[a-f0-9]{7,40}$ ]]; then
    echo "ERROR: Invalid ${version_file}: expected ${tool}-<7-to-40-char-hex-commit>, got '${version}'" >&2
    exit 1
  fi

  printf -v "${version_var}" "%s" "${version}"
  printf -v "${commit_var}" "%s" "${commit}"
}

# Use the platform-appropriate SHA-256 utility.
sha256sum() {
  if type -P sha256sum &>/dev/null; then
    command sha256sum "$@"
  else
    shasum -a 256 "$@"
  fi
}

#
# Update espresso binary
# Args: $1 - native_only ("yes" to build only for native platform, "no" for both x64 and arm64)
#       $2 - force ("yes" to force rebuild even if release exists, "no" otherwise)
# Returns: 0 on success, exits with 1 on error
#
do_update_espresso() {
  local native_only=$1
  local force=${2:-no}

  # Requires: docker (for build_espresso_with_docker.sh) and gh (GitHub CLI, authenticated)
  if ! command -v gh &>/dev/null; then
    echo "ERROR: 'gh' CLI is required for 'chore update espresso'. Install from https://cli.github.com" >&2
    exit 1
  fi

  # ESPRESSO_VERSION is the source of truth for both the release tag and git commit.
  local espresso_version_file="${UDB_ROOT}/tools/ruby-gems/udb/lib/udb/ESPRESSO_VERSION"
  local espresso_version
  local espresso_commit
  read_git_pinned_tool_version espresso "${espresso_version_file}" espresso_version espresso_commit
  echo "==> Building espresso version: ${espresso_version} (commit: ${espresso_commit})"

  # Check if the GitHub Release exists
  local release_exists=no
  if gh release view "${espresso_version}" --repo riscv/riscv-unified-db &>/dev/null; then
    release_exists=yes
  fi

  # Handle based on force flag and release existence
  if [ "${force}" != "yes" ] && [ "${release_exists}" = "yes" ]; then
    echo "==> GitHub Release ${espresso_version} already exists. Nothing to do."
    echo "    Use -f flag to force rebuild."
    return 0
  fi

  if [ "${force}" = "yes" ] && [ "${release_exists}" = "yes" ]; then
    echo "==> Force rebuild enabled..."
    # Only delete the release if we're building both architectures (not native_only)
    # For native_only builds, we'll use --clobber to replace individual assets
    if [ "${native_only}" != "yes" ]; then
      echo "==> Deleting existing GitHub Release ${espresso_version}..."
      gh release delete "${espresso_version}" --repo riscv/riscv-unified-db --yes
    else
      echo "==> Will replace existing assets with --clobber"
    fi
  fi

  echo "==> Building espresso ${espresso_version}..."

  local orig_dir="${PWD}"
  local work_dir
  work_dir=$(mktemp -d "$PWD/build-espresso.XXXXXX")

  local current_os
  case "$(uname -s)" in
    Linux)  current_os="Linux" ;;
    Darwin) current_os="Mac" ;;
    *)
      echo "ERROR: Unsupported OS: $(uname -s)" >&2
      exit 1
      ;;
  esac

  if [ "${native_only}" = "yes" ]; then
    # Detect native architecture
    local native_arch
    case "$(uname -m)" in
      x86_64)
        native_arch="x64"
        ;;
      aarch64)
        native_arch="arm64"
        ;;
      *)
        echo "ERROR: Unsupported architecture: $(uname -m)" >&2
        exit 1
        ;;
    esac
    echo "==> Building espresso for native platform (${current_os}-${native_arch})..."
    if [ "${current_os}" = "Mac" ]; then
      "${UDB_ROOT}"/tools/scripts/build_espresso_mac.sh "${work_dir}/espresso-build" "${native_arch}" || exit 1
    else
      "${UDB_ROOT}"/tools/scripts/build_espresso_with_docker.sh "${work_dir}/espresso-build" "${native_arch}" || exit 1
    fi

    # Move the binary to the asset name expected by the gem
    mv "${work_dir}/espresso-build/espresso" "${work_dir}/espresso-${current_os}-${native_arch}"
    # Generate checksum
    echo "==> Generating checksum..."
    (cd "${work_dir}" && sha256sum "espresso-${current_os}-${native_arch}" | awk '{print "sha256:" $1}' > "espresso-${current_os}-${native_arch}.checksum")
    echo "  ${current_os}-${native_arch}: $(cat "${work_dir}/espresso-${current_os}-${native_arch}.checksum")"

    echo "==> Uploading ${current_os}-${native_arch} assets to GitHub Release ${espresso_version}..."
    if ! gh release upload "${espresso_version}" \
      --repo riscv/riscv-unified-db \
      --clobber \
      "${work_dir}/espresso-${current_os}-${native_arch}" \
      "${work_dir}/espresso-${current_os}-${native_arch}.checksum" 2>/dev/null; then
      echo "==> Release doesn't exist yet, creating it..."
      gh release create "${espresso_version}" \
        --repo riscv/riscv-unified-db \
        --title "Espresso binaries ${espresso_version}" \
        --notes "Pre-built espresso binaries for the udb gem (Linux and macOS, x64 and arm64). Commit: ${espresso_commit}" \
        "${work_dir}/espresso-${current_os}-${native_arch}" \
        "${work_dir}/espresso-${current_os}-${native_arch}.checksum"
    fi
  else
    echo "==> Building espresso for Linux-x64..."
    "${UDB_ROOT}"/tools/scripts/build_espresso_with_docker.sh "${work_dir}/espresso-Linux-x64-out" x64 || exit 1

    echo "==> Building espresso for Linux-arm64..."
    "${UDB_ROOT}"/tools/scripts/build_espresso_with_docker.sh "${work_dir}/espresso-Linux-arm64-out" arm64 || exit 1

    mv "${work_dir}/espresso-Linux-x64-out/espresso"   "${work_dir}/espresso-Linux-x64"
    mv "${work_dir}/espresso-Linux-arm64-out/espresso" "${work_dir}/espresso-Linux-arm64"

    if [ "${current_os}" = "Mac" ]; then
      echo "==> Building espresso for Mac-x64..."
      "${UDB_ROOT}"/tools/scripts/build_espresso_mac.sh "${work_dir}/espresso-Mac-x64-out" x64 || exit 1

      echo "==> Building espresso for Mac-arm64..."
      "${UDB_ROOT}"/tools/scripts/build_espresso_mac.sh "${work_dir}/espresso-Mac-arm64-out" arm64 || exit 1

      mv "${work_dir}/espresso-Mac-x64-out/espresso"   "${work_dir}/espresso-Mac-x64"
      mv "${work_dir}/espresso-Mac-arm64-out/espresso" "${work_dir}/espresso-Mac-arm64"
    else
      echo "==> WARNING: Skipping Mac build — run this on a macOS runner to produce Mac assets."
    fi

    echo "==> Generating checksums..."
    (cd "${work_dir}" && sha256sum espresso-Linux-x64   | awk '{print "sha256:" $1}' > espresso-Linux-x64.checksum)
    (cd "${work_dir}" && sha256sum espresso-Linux-arm64 | awk '{print "sha256:" $1}' > espresso-Linux-arm64.checksum)
    echo "  Linux-x64:   $(cat "${work_dir}/espresso-Linux-x64.checksum")"
    echo "  Linux-arm64: $(cat "${work_dir}/espresso-Linux-arm64.checksum")"

    local release_assets=(
      "${work_dir}/espresso-Linux-x64"
      "${work_dir}/espresso-Linux-arm64"
      "${work_dir}/espresso-Linux-x64.checksum"
      "${work_dir}/espresso-Linux-arm64.checksum"
    )

    if [ "${current_os}" = "Mac" ]; then
      (cd "${work_dir}" && sha256sum espresso-Mac-x64   | awk '{print "sha256:" $1}' > espresso-Mac-x64.checksum)
      (cd "${work_dir}" && sha256sum espresso-Mac-arm64 | awk '{print "sha256:" $1}' > espresso-Mac-arm64.checksum)
      echo "  Mac-x64:   $(cat "${work_dir}/espresso-Mac-x64.checksum")"
      echo "  Mac-arm64: $(cat "${work_dir}/espresso-Mac-arm64.checksum")"
      release_assets+=(
        "${work_dir}/espresso-Mac-x64"
        "${work_dir}/espresso-Mac-arm64"
        "${work_dir}/espresso-Mac-x64.checksum"
        "${work_dir}/espresso-Mac-arm64.checksum"
      )
    fi

    echo "==> Creating GitHub Release ${espresso_version}..."
    gh release create "${espresso_version}" \
      --repo riscv/riscv-unified-db \
      --title "Espresso binaries ${espresso_version}" \
      --notes "Pre-built espresso binaries for the udb gem (Linux and macOS, x64 and arm64). Commit: ${espresso_commit}" \
      "${release_assets[@]}"
  fi

  cd "${orig_dir}" || exit 1
  rm -rf "${work_dir}"

  echo ""
  echo "Done. GitHub Release ${espresso_version} created on riscv/riscv-unified-db."
}

#
# Update must binary
# Args: $1 - native_only ("yes" to build only for native platform, "no" for both x64 and arm64)
#       $2 - force ("yes" to force rebuild even if release exists, "no" otherwise)
# Returns: 0 on success, exits with 1 on error
#
do_update_must() {
  local native_only=$1
  local force=${2:-no}

  # Requires: docker (for build_must_with_docker.sh) and gh (GitHub CLI, authenticated)
  if ! command -v gh &>/dev/null; then
    echo "ERROR: 'gh' CLI is required for 'chore update must'. Install from https://cli.github.com" >&2
    exit 1
  fi

  # MUST_VERSION is the source of truth for both the release tag and git commit.
  local must_version_file="${UDB_ROOT}/tools/ruby-gems/udb/lib/udb/MUST_VERSION"
  local must_version
  local must_commit
  read_git_pinned_tool_version must "${must_version_file}" must_version must_commit
  echo "==> Building must version: ${must_version} (commit: ${must_commit})"

  # Check if the GitHub Release exists
  local release_exists=no
  if gh release view "${must_version}" --repo riscv/riscv-unified-db &>/dev/null; then
    release_exists=yes
  fi

  # Handle based on force flag and release existence
  if [ "${force}" != "yes" ] && [ "${release_exists}" = "yes" ]; then
    echo "==> GitHub Release ${must_version} already exists. Nothing to do."
    echo "    Use -f flag to force rebuild."
    return 0
  fi

  if [ "${force}" = "yes" ] && [ "${release_exists}" = "yes" ]; then
    echo "==> Force rebuild enabled..."
    # Only delete the release if we're building both architectures (not native_only)
    # For native_only builds, we'll use --clobber to replace individual assets
    if [ "${native_only}" != "yes" ]; then
      echo "==> Deleting existing GitHub Release ${must_version}..."
      gh release delete "${must_version}" --repo riscv/riscv-unified-db --yes
    else
      echo "==> Will replace existing assets with --clobber"
    fi
  fi

  echo "==> Building must ${must_version}..."

  local orig_dir="${PWD}"
  local work_dir
  work_dir=$(mktemp -d "$PWD/build-must.XXXXXX")

  local current_os
  case "$(uname -s)" in
    Linux)  current_os="Linux" ;;
    Darwin) current_os="Mac" ;;
    *)
      echo "ERROR: Unsupported OS: $(uname -s)" >&2
      exit 1
      ;;
  esac

  if [ "${native_only}" = "yes" ]; then
    # Detect native architecture
    local native_arch
    case "$(uname -m)" in
      x86_64)
        native_arch="x64"
        ;;
      aarch64)
        native_arch="arm64"
        ;;
      *)
        echo "ERROR: Unsupported architecture: $(uname -m)" >&2
        exit 1
        ;;
    esac
    echo "==> Building must for native platform (${current_os}-${native_arch})..."
    if [ "${current_os}" = "Mac" ]; then
      "${UDB_ROOT}"/tools/scripts/build_must_mac.sh "${work_dir}/must-build" "${native_arch}" || exit 1
    else
      "${UDB_ROOT}"/tools/scripts/build_must_with_docker.sh "${work_dir}/must-build" "${native_arch}" || exit 1
    fi

    # Move the binary to the asset name expected by the gem
    mv "${work_dir}/must-build/must" "${work_dir}/must-${current_os}-${native_arch}"
    # Generate checksum
    echo "==> Generating checksum..."
    (cd "${work_dir}" && sha256sum "must-${current_os}-${native_arch}" | awk '{print "sha256:" $1}' > "must-${current_os}-${native_arch}.checksum")
    echo "  ${current_os}-${native_arch}: $(cat "${work_dir}/must-${current_os}-${native_arch}.checksum")"

    echo "==> Uploading ${current_os}-${native_arch} assets to GitHub Release ${must_version}..."
    if ! gh release upload "${must_version}" \
      --repo riscv/riscv-unified-db \
      --clobber \
      "${work_dir}/must-${current_os}-${native_arch}" \
      "${work_dir}/must-${current_os}-${native_arch}.checksum" 2>/dev/null; then
      echo "==> Release doesn't exist yet, creating it..."
      gh release create "${must_version}" \
        --repo riscv/riscv-unified-db \
        --title "Must binaries ${must_version}" \
        --notes "Pre-built must binaries for the udb gem (Linux and macOS, x64 and arm64). Commit: ${must_commit}" \
        "${work_dir}/must-${current_os}-${native_arch}" \
        "${work_dir}/must-${current_os}-${native_arch}.checksum"
    fi
  else
    echo "==> Building must for Linux-x64..."
    "${UDB_ROOT}"/tools/scripts/build_must_with_docker.sh "${work_dir}/must-Linux-x64-out" x64 || exit 1

    echo "==> Building must for Linux-arm64..."
    "${UDB_ROOT}"/tools/scripts/build_must_with_docker.sh "${work_dir}/must-Linux-arm64-out" arm64 || exit 1

    mv "${work_dir}/must-Linux-x64-out/must"   "${work_dir}/must-Linux-x64"
    mv "${work_dir}/must-Linux-arm64-out/must" "${work_dir}/must-Linux-arm64"

    if [ "${current_os}" = "Mac" ]; then
      echo "==> Building must for Mac-x64..."
      "${UDB_ROOT}"/tools/scripts/build_must_mac.sh "${work_dir}/must-Mac-x64-out" x64 || exit 1

      echo "==> Building must for Mac-arm64..."
      "${UDB_ROOT}"/tools/scripts/build_must_mac.sh "${work_dir}/must-Mac-arm64-out" arm64 || exit 1

      mv "${work_dir}/must-Mac-x64-out/must"   "${work_dir}/must-Mac-x64"
      mv "${work_dir}/must-Mac-arm64-out/must" "${work_dir}/must-Mac-arm64"
    else
      echo "==> WARNING: Skipping Mac build — run this on a macOS runner to produce Mac assets."
    fi

    echo "==> Generating checksums..."
    (cd "${work_dir}" && sha256sum must-Linux-x64   | awk '{print "sha256:" $1}' > must-Linux-x64.checksum)
    (cd "${work_dir}" && sha256sum must-Linux-arm64 | awk '{print "sha256:" $1}' > must-Linux-arm64.checksum)
    echo "  Linux-x64:   $(cat "${work_dir}/must-Linux-x64.checksum")"
    echo "  Linux-arm64: $(cat "${work_dir}/must-Linux-arm64.checksum")"

    local release_assets=(
      "${work_dir}/must-Linux-x64"
      "${work_dir}/must-Linux-arm64"
      "${work_dir}/must-Linux-x64.checksum"
      "${work_dir}/must-Linux-arm64.checksum"
    )

    if [ "${current_os}" = "Mac" ]; then
      (cd "${work_dir}" && sha256sum must-Mac-x64   | awk '{print "sha256:" $1}' > must-Mac-x64.checksum)
      (cd "${work_dir}" && sha256sum must-Mac-arm64 | awk '{print "sha256:" $1}' > must-Mac-arm64.checksum)
      echo "  Mac-x64:   $(cat "${work_dir}/must-Mac-x64.checksum")"
      echo "  Mac-arm64: $(cat "${work_dir}/must-Mac-arm64.checksum")"
      release_assets+=(
        "${work_dir}/must-Mac-x64"
        "${work_dir}/must-Mac-arm64"
        "${work_dir}/must-Mac-x64.checksum"
        "${work_dir}/must-Mac-arm64.checksum"
      )
    fi

    echo "==> Creating GitHub Release ${must_version}..."
    gh release create "${must_version}" \
      --repo riscv/riscv-unified-db \
      --title "Must binaries ${must_version}" \
      --notes "Pre-built must binaries for the udb gem (Linux and macOS, x64 and arm64). Commit: ${must_commit}" \
      "${release_assets[@]}"
  fi

  cd "${orig_dir}" || exit 1
  rm -rf "${work_dir}"

  echo ""
  echo "Done. GitHub Release ${must_version} created on riscv/riscv-unified-db."
}

#
# Update eqntott binary
# Args: $1 - native_only ("yes" to build only for native platform, "no" for both x64 and arm64)
#       $2 - force ("yes" to force rebuild even if release exists, "no" otherwise)
# Returns: 0 on success, exits with 1 on error
#
do_update_eqntott() {
  local native_only=$1
  local force=${2:-no}

  # Requires: docker (for build_eqntott_with_docker.sh) and gh (GitHub CLI, authenticated)
  if ! command -v gh &>/dev/null; then
    echo "ERROR: 'gh' CLI is required for 'chore update eqntott'. Install from https://cli.github.com" >&2
    exit 1
  fi

  # EQNTOTT_VERSION is the source of truth for both the release tag and git commit.
  local eqntott_version_file="${UDB_ROOT}/tools/ruby-gems/udb/lib/udb/EQNTOTT_VERSION"
  local eqntott_version
  local eqntott_commit
  read_git_pinned_tool_version eqntott "${eqntott_version_file}" eqntott_version eqntott_commit
  echo "==> Building eqntott version: ${eqntott_version} (commit: ${eqntott_commit})"

  # Check if the GitHub Release exists
  local release_exists=no
  if gh release view "${eqntott_version}" --repo riscv/riscv-unified-db &>/dev/null; then
    release_exists=yes
  fi

  # Handle based on force flag and release existence
  if [ "${force}" != "yes" ] && [ "${release_exists}" = "yes" ]; then
    echo "==> GitHub Release ${eqntott_version} already exists. Nothing to do."
    echo "    Use -f flag to force rebuild."
    return 0
  fi

  if [ "${force}" = "yes" ] && [ "${release_exists}" = "yes" ]; then
    echo "==> Force rebuild enabled..."
    # Only delete the release if we're building both architectures (not native_only)
    # For native_only builds, we'll use --clobber to replace individual assets
    if [ "${native_only}" != "yes" ]; then
      echo "==> Deleting existing GitHub Release ${eqntott_version}..."
      gh release delete "${eqntott_version}" --repo riscv/riscv-unified-db --yes
    else
      echo "==> Will replace existing assets with --clobber"
    fi
  fi

  echo "==> Building eqntott ${eqntott_version}..."

  local orig_dir="${PWD}"
  local work_dir
  work_dir=$(mktemp -d "$PWD/build-eqntott.XXXXXX")

  local current_os
  case "$(uname -s)" in
    Linux)  current_os="Linux" ;;
    Darwin) current_os="Mac" ;;
    *)
      echo "ERROR: Unsupported OS: $(uname -s)" >&2
      exit 1
      ;;
  esac

  if [ "${native_only}" = "yes" ]; then
    # Detect native architecture
    local native_arch
    case "$(uname -m)" in
      x86_64)
        native_arch="x64"
        ;;
      aarch64)
        native_arch="arm64"
        ;;
      *)
        echo "ERROR: Unsupported architecture: $(uname -m)" >&2
        exit 1
        ;;
    esac
    echo "==> Building eqntott for native platform (${current_os}-${native_arch})..."
    if [ "${current_os}" = "Mac" ]; then
      "${UDB_ROOT}"/tools/scripts/build_eqntott_mac.sh "${work_dir}/eqntott-build" "${native_arch}" || exit 1
    else
      "${UDB_ROOT}"/tools/scripts/build_eqntott_with_docker.sh "${work_dir}/eqntott-build" "${native_arch}" || exit 1
    fi

    # Move the binary to the asset name expected by the gem
    mv "${work_dir}/eqntott-build/eqntott" "${work_dir}/eqntott-${current_os}-${native_arch}"
    # Generate checksum
    echo "==> Generating checksum..."
    (cd "${work_dir}" && sha256sum "eqntott-${current_os}-${native_arch}" | awk '{print "sha256:" $1}' > "eqntott-${current_os}-${native_arch}.checksum")
    echo "  ${current_os}-${native_arch}: $(cat "${work_dir}/eqntott-${current_os}-${native_arch}.checksum")"

    echo "==> Uploading ${current_os}-${native_arch} assets to GitHub Release ${eqntott_version}..."
    # Try to upload; if release doesn't exist, create it first (for parallel CI builds)
    if ! gh release upload "${eqntott_version}" \
      --repo riscv/riscv-unified-db \
      --clobber \
      "${work_dir}/eqntott-${current_os}-${native_arch}" \
      "${work_dir}/eqntott-${current_os}-${native_arch}.checksum" 2>/dev/null; then
      echo "==> Release doesn't exist yet, creating it..."
      gh release create "${eqntott_version}" \
        --repo riscv/riscv-unified-db \
        --title "eqntott binaries ${eqntott_version}" \
        --notes "Pre-built eqntott binaries for the udb gem (Linux and macOS, x64 and arm64). Commit: ${eqntott_commit}" \
        "${work_dir}/eqntott-${current_os}-${native_arch}" \
        "${work_dir}/eqntott-${current_os}-${native_arch}.checksum"
    fi
  else
    echo "==> Building eqntott for Linux-x64..."
    "${UDB_ROOT}"/tools/scripts/build_eqntott_with_docker.sh "${work_dir}/eqntott-Linux-x64-out" x64 || exit 1

    echo "==> Building eqntott for Linux-arm64..."
    "${UDB_ROOT}"/tools/scripts/build_eqntott_with_docker.sh "${work_dir}/eqntott-Linux-arm64-out" arm64 || exit 1

    mv "${work_dir}/eqntott-Linux-x64-out/eqntott"   "${work_dir}/eqntott-Linux-x64"
    mv "${work_dir}/eqntott-Linux-arm64-out/eqntott" "${work_dir}/eqntott-Linux-arm64"

    if [ "${current_os}" = "Mac" ]; then
      echo "==> Building eqntott for Mac-x64..."
      "${UDB_ROOT}"/tools/scripts/build_eqntott_mac.sh "${work_dir}/eqntott-Mac-x64-out" x64 || exit 1

      echo "==> Building eqntott for Mac-arm64..."
      "${UDB_ROOT}"/tools/scripts/build_eqntott_mac.sh "${work_dir}/eqntott-Mac-arm64-out" arm64 || exit 1

      mv "${work_dir}/eqntott-Mac-x64-out/eqntott"   "${work_dir}/eqntott-Mac-x64"
      mv "${work_dir}/eqntott-Mac-arm64-out/eqntott" "${work_dir}/eqntott-Mac-arm64"
    else
      echo "==> WARNING: Skipping Mac build, run this on a macOS runner to produce Mac assets."
    fi

    echo "==> Generating checksums..."
    (cd "${work_dir}" && sha256sum eqntott-Linux-x64   | awk '{print "sha256:" $1}' > eqntott-Linux-x64.checksum)
    (cd "${work_dir}" && sha256sum eqntott-Linux-arm64 | awk '{print "sha256:" $1}' > eqntott-Linux-arm64.checksum)
    echo "  Linux-x64:   $(cat "${work_dir}/eqntott-Linux-x64.checksum")"
    echo "  Linux-arm64: $(cat "${work_dir}/eqntott-Linux-arm64.checksum")"

    local release_assets=(
      "${work_dir}/eqntott-Linux-x64"
      "${work_dir}/eqntott-Linux-arm64"
      "${work_dir}/eqntott-Linux-x64.checksum"
      "${work_dir}/eqntott-Linux-arm64.checksum"
    )

    if [ "${current_os}" = "Mac" ]; then
      (cd "${work_dir}" && sha256sum eqntott-Mac-x64   | awk '{print "sha256:" $1}' > eqntott-Mac-x64.checksum)
      (cd "${work_dir}" && sha256sum eqntott-Mac-arm64 | awk '{print "sha256:" $1}' > eqntott-Mac-arm64.checksum)
      echo "  Mac-x64:   $(cat "${work_dir}/eqntott-Mac-x64.checksum")"
      echo "  Mac-arm64: $(cat "${work_dir}/eqntott-Mac-arm64.checksum")"
      release_assets+=(
        "${work_dir}/eqntott-Mac-x64"
        "${work_dir}/eqntott-Mac-arm64"
        "${work_dir}/eqntott-Mac-x64.checksum"
        "${work_dir}/eqntott-Mac-arm64.checksum"
      )
    fi

    echo "==> Creating GitHub Release ${eqntott_version}..."
    gh release create "${eqntott_version}" \
      --repo riscv/riscv-unified-db \
      --title "eqntott binaries ${eqntott_version}" \
      --notes "Pre-built eqntott binaries for the udb gem (Linux and macOS, x64 and arm64). Commit: ${eqntott_commit}" \
      "${release_assets[@]}"
  fi

  cd "${orig_dir}" || exit 1
  rm -rf "${work_dir}"

  echo ""
  echo "Done. GitHub Release ${eqntott_version} created on riscv/riscv-unified-db."
}

#
# Update Z3 shared library
# Args: $1 - native_only ("yes" to build only for native platform, "no" for both x64 and arm64)
#       $2 - force ("yes" to force rebuild even if release exists, "no" otherwise)
# Returns: 0 on success, exits with 1 on error
#
do_update_z3() {
  local native_only=$1
  local force=${2:-no}

  # Requires: docker (for build_z3_with_docker.sh) and gh (GitHub CLI, authenticated)
  if ! command -v gh &>/dev/null; then
    echo "ERROR: 'gh' CLI is required for 'chore update z3'. Install from https://cli.github.com" >&2
    exit 1
  fi

  # Z3_VERSION is the source of truth for the release tag and upstream version.
  local z3_version_file="${UDB_ROOT}/tools/ruby-gems/udb/lib/udb/Z3_VERSION"
  local z3_version
  z3_version=$(<"${z3_version_file}") || {
    echo "ERROR: Could not read ${z3_version_file}" >&2
    exit 1
  }

  if [[ ! "${z3_version}" =~ ^z3-[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: Invalid ${z3_version_file}: expected z3-<major>.<minor>.<patch>, got '${z3_version}'" >&2
    exit 1
  fi

  echo "==> Building Z3 version: ${z3_version}"

  # Check if the GitHub Release exists
  local release_exists=no
  if gh release view "${z3_version}" --repo riscv/riscv-unified-db &>/dev/null; then
    release_exists=yes
  fi

  # Handle based on force flag and release existence
  if [ "${force}" != "yes" ] && [ "${release_exists}" = "yes" ]; then
    echo "==> GitHub Release ${z3_version} already exists. Nothing to do."
    echo "    Use -f flag to force rebuild."
    return 0
  fi

  if [ "${force}" = "yes" ] && [ "${release_exists}" = "yes" ]; then
    echo "==> Force rebuild enabled..."
    # Only delete the release if we're building both architectures (not native_only)
    # For native_only builds, we'll use --clobber to replace individual assets
    if [ "${native_only}" != "yes" ]; then
      echo "==> Deleting existing GitHub Release ${z3_version}..."
      gh release delete "${z3_version}" --repo riscv/riscv-unified-db --yes
    else
      echo "==> Will replace existing assets with --clobber"
    fi
  fi

  echo "==> Building Z3 ${z3_version}..."

  local orig_dir="${PWD}"
  local work_dir
  work_dir=$(mktemp -d "$PWD/build-z3.XXXXXX")

  local current_os
  case "$(uname -s)" in
    Linux)  current_os="Linux" ;;
    Darwin) current_os="Mac" ;;
    *)
      echo "ERROR: Unsupported OS: $(uname -s)" >&2
      exit 1
      ;;
  esac

  # Z3 uses .so on Linux and .dylib on macOS
  local lib_ext
  [ "${current_os}" = "Mac" ] && lib_ext="dylib" || lib_ext="so"

  if [ "${native_only}" = "yes" ]; then
    # Detect native architecture
    local native_arch
    case "$(uname -m)" in
      x86_64)
        native_arch="x64"
        ;;
      aarch64)
        native_arch="arm64"
        ;;
      *)
        echo "ERROR: Unsupported architecture: $(uname -m)" >&2
        exit 1
        ;;
    esac
    echo "==> Building Z3 for native platform (${current_os}-${native_arch})..."
    if [ "${current_os}" = "Mac" ]; then
      "${UDB_ROOT}"/tools/scripts/build_z3_mac.sh "${work_dir}/z3-${native_arch}" Release "${native_arch}" || exit 1
    else
      "${UDB_ROOT}"/tools/scripts/build_z3_with_docker.sh "${work_dir}/z3-${native_arch}" Release "${native_arch}" || exit 1
    fi

    local built_version
    built_version=$(cat "${work_dir}/z3-${native_arch}/VERSION")
    if [ "${built_version}" != "${z3_version}" ]; then
      echo "ERROR: Built Z3 version ${built_version} does not match ${z3_version}" >&2
      exit 1
    fi

    cp "${work_dir}/z3-${native_arch}/lib/libz3.${lib_ext}" "${work_dir}/libz3-${current_os}-${native_arch}.${lib_ext}"

    echo "==> Generating checksum..."
    (cd "${work_dir}" && sha256sum "libz3-${current_os}-${native_arch}.${lib_ext}" | awk '{print "sha256:" $1}' > "libz3-${current_os}-${native_arch}.checksum")
    echo "  ${current_os}-${native_arch}: $(cat "${work_dir}/libz3-${current_os}-${native_arch}.checksum")"

    echo "==> Uploading ${current_os}-${native_arch} assets to GitHub Release ${z3_version}..."
    if ! gh release upload "${z3_version}" \
      --repo riscv/riscv-unified-db \
      --clobber \
      "${work_dir}/libz3-${current_os}-${native_arch}.${lib_ext}" \
      "${work_dir}/libz3-${current_os}-${native_arch}.checksum" 2>/dev/null; then
      echo "==> Release doesn't exist yet, creating it..."
      gh release create "${z3_version}" \
        --repo riscv/riscv-unified-db \
        --title "Z3 binaries ${z3_version}" \
        --notes "Pre-built Z3 shared libraries for the udb gem (Linux and macOS, x64 and arm64)." \
        "${work_dir}/libz3-${current_os}-${native_arch}.${lib_ext}" \
        "${work_dir}/libz3-${current_os}-${native_arch}.checksum"
    fi
  else
    echo "==> Building Z3 for Linux-x64..."
    "${UDB_ROOT}"/tools/scripts/build_z3_with_docker.sh "${work_dir}/z3-Linux-x64" Release x64 || exit 1

    echo "==> Building Z3 for Linux-arm64..."
    "${UDB_ROOT}"/tools/scripts/build_z3_with_docker.sh "${work_dir}/z3-Linux-arm64" Release arm64 || exit 1

    local built_version
    built_version=$(cat "${work_dir}/z3-Linux-x64/VERSION")
    if [ "${built_version}" != "${z3_version}" ]; then
      echo "ERROR: Built Z3 version ${built_version} does not match ${z3_version}" >&2
      exit 1
    fi

    cp "${work_dir}/z3-Linux-x64/lib/libz3.so"   "${work_dir}/libz3-Linux-x64.so"
    cp "${work_dir}/z3-Linux-arm64/lib/libz3.so" "${work_dir}/libz3-Linux-arm64.so"

    if [ "${current_os}" = "Mac" ]; then
      echo "==> Building Z3 for Mac-x64..."
      "${UDB_ROOT}"/tools/scripts/build_z3_mac.sh "${work_dir}/z3-Mac-x64" Release x64 || exit 1

      echo "==> Building Z3 for Mac-arm64..."
      "${UDB_ROOT}"/tools/scripts/build_z3_mac.sh "${work_dir}/z3-Mac-arm64" Release arm64 || exit 1

      cp "${work_dir}/z3-Mac-x64/lib/libz3.dylib"   "${work_dir}/libz3-Mac-x64.dylib"
      cp "${work_dir}/z3-Mac-arm64/lib/libz3.dylib" "${work_dir}/libz3-Mac-arm64.dylib"
    else
      echo "==> WARNING: Skipping Mac build, run this on a macOS runner to produce Mac assets."
    fi

    echo "==> Generating checksums..."
    (cd "${work_dir}" && sha256sum libz3-Linux-x64.so   | awk '{print "sha256:" $1}' > libz3-Linux-x64.checksum)
    (cd "${work_dir}" && sha256sum libz3-Linux-arm64.so | awk '{print "sha256:" $1}' > libz3-Linux-arm64.checksum)
    echo "  Linux-x64:   $(cat "${work_dir}/libz3-Linux-x64.checksum")"
    echo "  Linux-arm64: $(cat "${work_dir}/libz3-Linux-arm64.checksum")"

    local release_assets=(
      "${work_dir}/libz3-Linux-x64.so"
      "${work_dir}/libz3-Linux-arm64.so"
      "${work_dir}/libz3-Linux-x64.checksum"
      "${work_dir}/libz3-Linux-arm64.checksum"
    )

    if [ "${current_os}" = "Mac" ]; then
      (cd "${work_dir}" && sha256sum libz3-Mac-x64.dylib   | awk '{print "sha256:" $1}' > libz3-Mac-x64.checksum)
      (cd "${work_dir}" && sha256sum libz3-Mac-arm64.dylib | awk '{print "sha256:" $1}' > libz3-Mac-arm64.checksum)
      echo "  Mac-x64:   $(cat "${work_dir}/libz3-Mac-x64.checksum")"
      echo "  Mac-arm64: $(cat "${work_dir}/libz3-Mac-arm64.checksum")"
      release_assets+=(
        "${work_dir}/libz3-Mac-x64.dylib"
        "${work_dir}/libz3-Mac-arm64.dylib"
        "${work_dir}/libz3-Mac-x64.checksum"
        "${work_dir}/libz3-Mac-arm64.checksum"
      )
    fi

    echo "==> Creating GitHub Release ${z3_version}..."
    gh release create "${z3_version}" \
      --repo riscv/riscv-unified-db \
      --title "Z3 binaries ${z3_version}" \
      --notes "Pre-built Z3 shared libraries for the udb gem (Linux and macOS, x64 and arm64)." \
      "${release_assets[@]}"
  fi

  cd "${orig_dir}" || exit 1
  rm -rf "${work_dir}"

  echo ""
  echo "Done. GitHub Release ${z3_version} created on riscv/riscv-unified-db."
}
