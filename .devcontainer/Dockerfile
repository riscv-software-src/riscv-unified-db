FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /workspace

RUN export DEBIAN_FRONTEND=noninteractive

# please keep pkgs sorted
RUN \
  apt-get update && \
  apt-get install -y --no-install-recommends --fix-missing \
    build-essential \
    bundler \
    clang-format \
    clang-tidy \
    cmake \
    ditaa \
    g++ \
    gcc-riscv64-linux-gnu \
    gcc-riscv64-unknown-elf \
    gdb \
    gh \
    git \
    less \
    libc6-dev-riscv64-cross \
    libelf-dev \
    libgmp-dev \
    libyaml-dev \
    nodejs \
    npm \
    python3 \
    python3-pip \
    python3.12-venv \
    ruby \
    ruby-dev \
    shellcheck

RUN apt-get clean autoclean
RUN apt-get autoremove -y
RUN rm -rf /var/lib/{apt,dpkg,cache,log}/*

WORKDIR /workspace
