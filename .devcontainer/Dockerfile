FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

WORKDIR /workspace

# Install system dependencies
# Note: nodejs, npm, python3 are now installed via mise for better version control
RUN apt-get update && \
  apt-get install -y --no-install-recommends --fix-missing \
  build-essential \
  ca-certificates \
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
  libffi-dev \
  libgmp-dev \
  liblzma-dev \
  libnewlib-dev \
  libreadline-dev \
  libsqlite3-dev \
  libssl-dev \
  libyaml-dev \
  libz3-dev \
  minisat \
  parallel \
  rustc \
  shellcheck \
  sudo \
  tk-dev \
  xz-utils \
  zlib1g-dev \
  \
  && apt-get clean autoclean \
  && apt-get autoremove -y \
  && rm -rf /var/lib/{apt,dpkg,cache,log}/*

# Install mise for unified tool version management
# This manages Ruby, Node.js, and Python versions
RUN curl https://mise.run | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy version configuration files
COPY .mise.toml /opt/.mise.toml
COPY .ruby-version /opt/.ruby-version

# Install tools via mise (Ruby, Node.js, Python)
WORKDIR /opt
RUN mise trust /opt/.mise.toml && \
    MISE_NODE_VERIFY=0 mise install --yes && \
    mise reshim
ENV PATH="/root/.local/share/mise/shims:$PATH"
ENV MISE_DATA_DIR="/root/.local/share/mise"
ENV RUBY_YJIT_ENABLE=1

# Verify installations
RUN ruby --version && \
    node --version && \
    npm --version && \
    python3 --version

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
RUN python3 -m venv /opt/venv && \
  /opt/venv/bin/pip install --no-cache-dir -r /opt/requirements.txt && \
  rm /opt/requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

# Install npm packages globally in the container
# The newer npm from mise (>= 10.2.0) fixes Podman UID/GID issues (npm/cli#5998)
COPY package.json package-lock.json /opt/node/
RUN cd /opt/node && \
  npm ci --no-audit --no-fund && \
  chown -R root:root /opt/node/node_modules && \
  rm /opt/node/package.json /opt/node/package-lock.json
ENV NODE_PATH="/opt/node/node_modules"
ENV PATH="/opt/node/node_modules/.bin:$PATH"
ENV IN_UDB_CONTAINER=true

# install gems
COPY Gemfile /opt/Gemfile
COPY Gemfile.lock /opt/Gemfile.lock
COPY tools/ruby-gems/idlc/idlc.gemspec /opt/tools/ruby-gems/idlc/
COPY tools/ruby-gems/idlc/lib/gem_versions.rb /opt/tools/ruby-gems/idlc/lib/
COPY tools/ruby-gems/idlc/lib/idlc/version.rb /opt/tools/ruby-gems/idlc/lib/idlc/
COPY tools/ruby-gems/idl_highlighter/idl_highlighter.gemspec /opt/tools/ruby-gems/idl_highlighter/
COPY tools/ruby-gems/idl_highlighter/lib/idl_highlighter/version.rb /opt/tools/ruby-gems/idl_highlighter/lib/idl_highlighter/
COPY tools/ruby-gems/udb/udb.gemspec /opt/tools/ruby-gems/udb/
COPY tools/ruby-gems/udb/lib/gem_versions.rb /opt/tools/ruby-gems/udb/lib/
COPY tools/ruby-gems/udb/lib/udb/version.rb /opt/tools/ruby-gems/udb/lib/udb/
COPY tools/ruby-gems/udb-gen/udb-gen.gemspec /opt/tools/ruby-gems/udb-gen/
COPY tools/ruby-gems/udb-gen/lib/gem_versions.rb /opt/tools/ruby-gems/udb-gen/lib/
COPY tools/ruby-gems/udb-gen/lib/udb-gen/version.rb /opt/tools/ruby-gems/udb-gen/lib/udb-gen/
COPY tools/ruby-gems/udb_helpers/udb_helpers.gemspec /opt/tools/ruby-gems/udb_helpers/
COPY tools/ruby-gems/udb_helpers/lib/udb_helpers/version.rb /opt/tools/ruby-gems/udb_helpers/lib/udb_helpers/
RUN bundle install --gemfile /opt/Gemfile

# the binaries for gems need to be copied in
RUN mkdir -p /workspace/bin/container
COPY tools/ruby-gems/idlc/bin/idlc /workspace/bin/container
COPY tools/ruby-gems/udb/bin/udb /workspace/bin/container
COPY tools/ruby-gems/udb-gen/bin/udb-gen /workspace/bin/container
ENV PATH="/workspace/bin/container:$PATH"

# Grant the default ubuntu user sudo access
RUN echo ubuntu ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/ubuntu \
    && chmod 0440 /etc/sudoers.d/ubuntu
