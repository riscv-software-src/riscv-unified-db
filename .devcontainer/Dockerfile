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
RUN set -eux; \
    git clone https://github.com/rbenv/rbenv.git /opt/rbenv; \
    export RBENV_ROOT=/opt/.rbenv; \
    git clone https://github.com/rbenv/ruby-build.git "$(/opt/rbenv/bin/rbenv root)/plugins/ruby-build"; \
    /opt/rbenv/bin/rbenv install "$(tr -d '\n' < /opt/.ruby-version)"; \
    /opt/rbenv/bin/rbenv global "$(tr -d '\n' < /opt/.ruby-version)"; \
    /opt/rbenv/bin/rbenv init - > /opt/.rbenv-init

# build/install eqntott
RUN set -eux; \
    git clone --depth=1 https://github.com/TheProjecter/eqntott.git; \
    cd eqntott; \
    ./configure; \
    make; \
    make install; \
    cd ..; \
    rm -rf eqntott


# build/install espresso
RUN set -eux; \
    git clone --depth=1 https://github.com/psksvp/espresso-ab-1.0.git; \
    cd espresso-ab-1.0; \
    ./configure; \
    make; \
    make install; \
    cd ..; \
    rm -rf espresso-ab-1.0

# build / install must
RUN set -eux; \
    git clone https://github.com/jar-ben/mustool.git; \
    cd mustool; \
    git checkout 17fa9f9542a9ce05328dfccd1cd410f05f741ab3; \
    sed -i -e 's/#include <signal.h>/#include <signal.h>\n#include <cstdio>/' mcsmus/mcsmus/control.cc; \
    make -j$(nproc); \
    install must -m 0777 /usr/bin/must; \
    cd ..; \
    rm -rf mustool

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

# Add rbenv initialization to all shells (login and interactive)
RUN echo 'eval "$(/opt/rbenv/bin/rbenv init -)"' >> /etc/bash.bashrc && \
    echo 'eval "$(/opt/rbenv/bin/rbenv init -)"' > /etc/profile.d/rbenv.sh
ENV RBENV_ROOT=/opt/.rbenv
ENV RUBY_YJIT_ENABLE=1

WORKDIR /workspace

COPY .devcontainer/docker-entrypoint.sh /
RUN chmod a+x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
