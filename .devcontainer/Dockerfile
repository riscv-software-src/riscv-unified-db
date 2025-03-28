FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /workspace

RUN export DEBIAN_FRONTEND=noninteractive
RUN apt-get update
RUN apt-get install -y --no-install-recommends git \
                                               gh \
                                               less \
                                               python3 \
                                               python3.12-venv \
                                               python3-pip \
                                               build-essential \
                                               ruby \
                                               ruby-dev \
                                               bundler \
                                               nodejs \
                                               npm \
                                               ditaa \
                                               libyaml-dev \
                                               cmake \
                                               g++ \
                                               clang-format \
                                               clang-tidy \
                                               libelf-dev \
                                               gcc-riscv64-unknown-elf \
                                               shellcheck
RUN apt-get clean autoclean
RUN apt-get autoremove -y
RUN rm -rf /var/lib/{apt,dpkg,cache,log}/*

WORKDIR /workspace
