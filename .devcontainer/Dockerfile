FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

WORKDIR /workspace

# please keep pkgs sorted
RUN apt-get update && \
  apt-get install -y --no-install-recommends --fix-missing \
  build-essential \
  clang-format \
  clang-tidy \
  cmake \
  curl \
  ditaa \
  g++ \
  gcc-riscv64-linux-gnu \
  gcc-riscv64-unknown-elf \
  gdb \
  gh \
  git \
  gpg \
  less \
  libc6-dev-riscv64-cross \
  libelf-dev \
  libgmp-dev \
  libnewlib-dev \
  libyaml-dev \
  libz3-dev \
  minisat \
  nodejs \
  npm \
  parallel \
  python3 \
  python3-pip \
  python3.12-venv \
  rustc \
  shellcheck \
  sudo \
  zlib1g-dev \
  \
  && apt-get clean autoclean \
  && apt-get autoremove -y \
  && rm -rf /var/lib/{apt,dpkg,cache,log}/*

  # build / install ruby
COPY .ruby-version /opt/.ruby-version
ENV RUBY_YJIT_ENABLE=1
RUN git clone --depth=1 https://github.com/rbenv/ruby-build.git && \
    cd ruby-build && \
    ./bin/ruby-build $(cat /opt/.ruby-version | tr -d "\n") /usr && \
    cd .. && \
    rm -rf ruby-build

# build/install eqntott
RUN git clone --depth=1 https://github.com/TheProjecter/eqntott.git && \
    cd eqntott && \
    ./configure && \
    make && make install && \
    cd .. && \
    rm -rf eqntott

# build/install espresso
RUN git clone --depth=1 https://github.com/psksvp/espresso-ab-1.0.git && \
    cd espresso-ab-1.0 && \
    ./configure && \
    make && make install && \
    cd .. && \
    rm -rf espresso-ab-1.0

# build / install must
# mcsmus/mcsmus/control.cc is missing #include <cstdio>, thus the sed below
RUN git clone https://github.com/jar-ben/mustool.git && \
    cd mustool && \
    git checkout 17fa9f9542a9ce05328dfccd1cd410f05f741ab3 && \
    sed -i -e 's/#include <signal.h>/#include <signal.h>\n#include <cstdio>/' mcsmus/mcsmus/control.cc && \
    make -j && \
    install must -m 0777 /usr/bin/must && \
    cd .. && \
    rm -rf mustool

# Create Python virtual environment and install packages
COPY requirements.txt /opt/requirements.txt
RUN /usr/bin/python3 -m venv /opt/venv && \
  /opt/venv/bin/pip install -r /opt/requirements.txt && \
  rm /opt/requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

# Install npm packages globally in the container
COPY package.json package-lock.json /opt/node/
RUN cd /opt/node && \
  /usr/bin/npm ci && \
  rm /opt/node/package.json /opt/node/package-lock.json
ENV NODE_PATH="/opt/node/node_modules"
ENV PATH="/opt/node/node_modules/.bin:$PATH"
ENV IN_UDB_CONTAINER=true

# Grant the default ubuntu user sudo access
RUN echo ubuntu ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/ubuntu \
    && chmod 0440 /etc/sudoers.d/ubuntu
