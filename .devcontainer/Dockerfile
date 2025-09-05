FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Create a non-root user
RUN useradd -m -s /bin/bash vscode
 
WORKDIR /workspace
 
# Configure apt proxy settings if proxy environment variables are set
RUN if [ -n "$http_proxy" ] || [ -n "$https_proxy" ]; then \
mkdir -p /etc/apt/apt.conf.d && \
echo "Acquire::http::Proxy \"$http_proxy\";" > /etc/apt/apt.conf.d/01proxy; \
echo "Acquire::https::Proxy \"$https_proxy\";" >> /etc/apt/apt.conf.d/01proxy; \
else \
echo "No proxy environment variables set for apt" > /etc/apt/apt.conf.d/01proxy.notes; \
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
    shellcheck \
    curl

# Configure pip proxy settings
RUN if [ -n "$http_proxy" ] || [ -n "$https_proxy" ]; then \
mkdir -p /etc && \
echo "[global]" > /etc/pip.conf; \
if [ -n "$http_proxy" ]; then echo "proxy = $http_proxy" >> /etc/pip.conf; fi; \
if [ -n "$https_proxy" ]; then echo "trusted-host = pypi.org" >> /etc/pip.conf; \
echo "trusted-host = pypi.python.org" >> /etc/pip.conf; \
echo "trusted-host = files.pythonhosted.org" >> /etc/pip.conf; fi; \
else \
echo "No proxy environment variables set for pip" > /etc/pip.conf.notes; \
fi
 
# Configure npm proxy settings
RUN if [ -n "$http_proxy" ]; then npm config set proxy $http_proxy; fi
RUN if [ -n "$https_proxy" ]; then npm config set https-proxy $https_proxy; fi
 
# Configure bundler proxy settings
RUN if [ -n "$http_proxy" ]; then bundle config http_proxy $http_proxy; fi
RUN if [ -n "$https_proxy" ]; then bundle config https_proxy $https_proxy; fi
 
# Create a virtual environment for Python packages
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Install requirements in virtual environment
RUN if [ -f "/workspace/requirements.txt" ]; then \
pip install -r /workspace/requirements.txt; \
else \
echo "No requirements.txt found"; \
fi
 
RUN apt-get clean autoclean
RUN apt-get autoremove -y
RUN rm -rf /var/lib/{apt,dpkg,cache,log}/*
 
# Switch to non-root user
USER vscode
WORKDIR /home/vscode
