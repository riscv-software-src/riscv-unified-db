FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /workspace

RUN export DEBIAN_FRONTEND=noninteractive

# please keep pkgs sorted
RUN \
  apt-get update && \
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
    libnewlib-dev\
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
    zlib1g-dev

# build / install ruby
COPY .ruby-version /opt/.ruby-version
RUN <<CMDS
  git clone https://github.com/rbenv/rbenv.git /opt/rbenv
  export RBENV_ROOT=/opt/.rbenv
  git clone https://github.com/rbenv/ruby-build.git "$(/opt/rbenv/bin/rbenv root)"/plugins/ruby-build
  /opt/rbenv/bin/rbenv install $(cat /opt/.ruby-version | tr -d "\n")
  /opt/rbenv/bin/rbenv global $(cat /opt/.ruby-version | tr -d "\n")
  /opt/rbenv/bin/rbenv init - > /opt/.rbenv-init
CMDS

# build/install eqntott
RUN  <<CMDS
  git clone --depth=1 https://github.com/TheProjecter/eqntott.git
  cd eqntott
  ./configure
  make && make install
  cd ..
  rm -rf eqntott
CMDS

# build/install espresso
RUN <<CMDS
  git clone --depth=1 https://github.com/psksvp/espresso-ab-1.0.git
  cd espresso-ab-1.0
  ./configure
  make && make install
  cd ..
  rm -rf espresso-ab-1.0
CMDS

# build / install must
RUN <<CMDS
  git clone https://github.com/jar-ben/mustool.git
  cd mustool
  git checkout 17fa9f9542a9ce05328dfccd1cd410f05f741ab3
  # mcsmus/mcsmus/control.cc is missing #include <cstdio>
  sed -i -e 's/#include <signal.h>/#include <signal.h>\n#include <cstdio>/' mcsmus/mcsmus/control.cc
  make -j
  install must -m 0777 /usr/bin/must
  cd ..
  rm -rf mustool
CMDS

RUN apt-get clean autoclean
RUN apt-get autoremove -y
RUN rm -rf /var/lib/{apt,dpkg,cache,log}/*

# Create Python virtual environment and install packages
COPY requirements.txt /tmp/requirements.txt
RUN /usr/bin/python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt
ENV PATH="/opt/venv/bin:$PATH"

# Install npm packages globally in the container
COPY package.json package-lock.json /opt/node/
RUN cd /opt/node && \
    /usr/bin/npm ci && \
    rm /opt/node/package.json /opt/node/package-lock.json
ENV NODE_PATH="/opt/node/node_modules"
ENV PATH="/opt/node/node_modules/.bin:$PATH"

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
# Add rbenv initialization to all shells (login and interactive)
RUN export RBENV_ROOT=/opt/.rbenv && \
    echo 'eval "$(/opt/rbenv/bin/rbenv init -)"' >> /etc/bash.bashrc && \
    echo 'eval "$(/opt/rbenv/bin/rbenv init -)"' > /etc/profile.d/rbenv.sh
RUN <<CMDS
  export RBENV_ROOT=/opt/.rbenv
  eval "$(/opt/rbenv/bin/rbenv init -)"
  bundle install --gemfile /opt/Gemfile
CMDS

WORKDIR /workspace

COPY .devcontainer/docker-entrypoint.sh /
RUN chmod a+x /docker-entrypoint.sh

# the binaries for gems need to be copied in
RUN mkdir -p /workspace/bin/container
COPY tools/ruby-gems/idlc/bin/idlc /workspace/bin/container
COPY tools/ruby-gems/udb/bin/udb /workspace/bin/container
COPY tools/ruby-gems/udb-gen/bin/udb-gen /workspace/bin/container
ENV PATH="/workspace/bin/container:$PATH"

ENV RBENV_ROOT="/opt/.rbenv"
ENTRYPOINT ["/docker-entrypoint.sh"]
