FROM ubuntu:24.04

# Set environment variables for proxies (can be overridden at build time)
ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG NO_PROXY="localhost,127.0.0.1"

# Configure system-wide proxy settings
ENV http_proxy=$HTTP_PROXY \
    https_proxy=$HTTPS_PROXY \
    HTTP_PROXY=$HTTP_PROXY \
    HTTPS_PROXY=$HTTPS_PROXY \
    NO_PROXY=$NO_PROXY \
    DEBIAN_FRONTEND=noninteractive

# Configure apt to use proxy
RUN if [ ! -z "$HTTP_PROXY" ]; then \
    echo "Acquire::http::Proxy \"$HTTP_PROXY\";" > /etc/apt/apt.conf.d/proxy.conf && \
    echo "Acquire::https::Proxy \"$HTTPS_PROXY\";" >> /etc/apt/apt.conf.d/proxy.conf; \
    fi

WORKDIR /workspace

# Copy project files for installation
COPY . /workspace/

# Configure git to use proxy if needed
RUN if [ ! -z "$HTTP_PROXY" ]; then \
    git config --global http.proxy $HTTP_PROXY && \
    git config --global https.proxy $HTTPS_PROXY; \
    fi

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
    libnewlib-dev\
    libyaml-dev \
    nodejs \
    npm \
    parallel \
    python3 \
    python3-pip \
    python3.12-venv \
    ruby \
    ruby-dev \
    shellcheck && \
  apt-get clean autoclean && \
  apt-get autoremove -y && \
  rm -rf /var/lib/{apt,dpkg,cache,log}/*

# Configure pip to use proxy and install packages
RUN if [ ! -z "$HTTP_PROXY" ]; then \
    mkdir -p ~/.config/pip && \
    echo "[global]" > ~/.config/pip/pip.conf && \
    echo "proxy = $HTTP_PROXY" >> ~/.config/pip/pip.conf && \
    echo "https-proxy = $HTTPS_PROXY" >> ~/.config/pip/pip.conf; \
    fi && \
    python3 -m pip install --no-cache-dir -r requirements.txt

# Configure npm to use proxy and install packages
RUN if [ ! -z "$HTTP_PROXY" ]; then \
    npm config set proxy $HTTP_PROXY && \
    npm config set https-proxy $HTTPS_PROXY; \
    fi && \
    npm ci

# Configure bundler for proxy support
RUN if [ ! -z "$HTTP_PROXY" ]; then \
    bundle config mirror.https://rubygems.org/api/v1/dependencies https://rubygems.org/api/v1/dependencies && \
    bundle config mirror.https://rubygems.org/specs.4.8.gz https://rubygems.org/specs.4.8.gz && \
    bundle config mirror.https://rubygems.org/quick/Marshal.4.8/ https://rubygems.org/quick/Marshal.4.8/ && \
    bundle config mirror.https://rubygems.org https://rubygems.org && \
    bundle config --local http_proxy "$HTTP_PROXY" && \
    bundle config --local https_proxy "$HTTPS_PROXY"; \
    fi

# Install Ruby gems with retries for network stability
RUN bundle install --retry=3

# Create a non-root user
RUN useradd -m -s /bin/bash vscode && \
    chown -R vscode:vscode /workspace

USER vscode

WORKDIR /workspace
