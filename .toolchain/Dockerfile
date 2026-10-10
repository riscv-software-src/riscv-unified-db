# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear
#
# Toolchain container for riscv-unified-db.
# Based on AlmaLinux 8 + gcc-toolset-14 (same base as build_z3_with_docker.sh).
# The RISC-V GNU toolchain is built from source to ensure compatibility with
# AlmaLinux 8's glibc 2.28 (pre-built tarballs from riscv-collab require glibc >= 2.31).
#
# Build:
#   docker build --platform linux/amd64 -t udb-toolchain .
#   docker build --platform linux/arm64 -t udb-toolchain .
FROM almalinux:8@sha256:9f355ae942d6a6c0561f0771dc053a2cfae9580fc45fa4252756db7c7e80c09f
LABEL org.opencontainers.image.source=https://github.com/riscv/riscv-unified-db

# Install host C/C++ toolchain (gcc-toolset-14), make, gdb, clang
# (for clang-format/clang-tidy), and build dependencies.
# Build deps for riscv-gnu-toolchain: autoconf automake python3 libmpc-devel
# mpfr-devel gmp-devel gawk bison flex texinfo patchutils zlib-devel expat-devel
RUN dnf install -y dnf-plugins-core \
    && dnf config-manager --set-enabled powertools \
    && dnf install -y \
        gcc-toolset-14 \
        gcc-toolset-14-gcc-c++ \
        make \
        gdb \
        clang-tools-extra \
        elfutils-libelf-devel \
        gmp-devel \
        curl \
        git \
        autoconf \
        automake \
        python3 \
        libmpc-devel \
        mpfr-devel \
        gawk \
        bison \
        flex \
        texinfo \
        patchutils \
        zlib-devel \
        expat-devel \
    && dnf clean all

ENV PATH=/opt/rh/gcc-toolset-14/root/usr/bin:$PATH
ENV LD_LIBRARY_PATH=/opt/rh/gcc-toolset-14/root/usr/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}

# Build riscv-gnu-toolchain from source.
# Produces both:
#   riscv64-unknown-elf-gcc      (bare-metal ELF cross-compiler)
#   riscv64-unknown-linux-gnu-gcc (Linux glibc cross-compiler)
#
# Source: https://github.com/riscv-collab/riscv-gnu-toolchain
ARG RISCV_TOOLCHAIN_VERSION=2026.08.27

RUN set -e; \
    git clone --depth 1 --branch "${RISCV_TOOLCHAIN_VERSION}" \
        https://github.com/riscv-collab/riscv-gnu-toolchain \
        /tmp/riscv-gnu-toolchain; \
    cd /tmp/riscv-gnu-toolchain; \
    git config submodule.dejagnu.update none; \
    git submodule update --init --recursive --depth 1; \
    \
    # Configure for rv64gc / lp64d (no multilib — keeps build fast) \
    ./configure --prefix=/opt/riscv --with-arch=rv64gc --with-abi=lp64d; \
    \
    # Build bare-metal ELF toolchain (riscv64-unknown-elf-*) \
    make -j"$(nproc)"; \
    \
    # Build Linux-GNU (glibc) toolchain (riscv64-unknown-linux-gnu-*) \
    make linux -j"$(nproc)"; \
    \
    # Clean up source tree to reduce image size \
    cd /; \
    rm -rf /tmp/riscv-gnu-toolchain

ENV PATH=/opt/riscv/bin:$PATH
