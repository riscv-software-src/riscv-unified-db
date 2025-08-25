# RISC-V UnifiedDB Development Container

This directory contains the development container configuration for the RISC-V UnifiedDB project. The container is designed to work seamlessly in corporate environments with proxy restrictions.

## Features

- Comprehensive proxy support for:
  - apt-get package manager
  - pip (Python packages)
  - npm (Node.js packages)
  - bundle (Ruby gems)
  - git operations
- Pre-installed development tools and dependencies
- Non-root user setup for security
- Retry mechanisms for network stability
- All dependencies included in the container

## Quick Start

The pre-built container image is available on Docker Hub at `riscvintl/udb`. To use it:

1. Clone the repository:
   ```bash
   git clone https://github.com/riscv-software-src/riscv-unified-db.git
   cd riscv-unified-db
   ```

2. Open in VS Code with the Dev Containers extension installed:
   ```bash
   code .
   ```

3. When prompted, click "Reopen in Container" or use the Command Palette (F1) and select "Dev Containers: Reopen in Container"

### Proxy Configuration

If you're behind a corporate proxy:

1. Set your proxy environment variables:
   ```bash
   export http_proxy="http://your-proxy:port"
   export https_proxy="http://your-proxy:port"
   ```

2. The development container will automatically use these proxy settings when building and running.

## Building the Container Locally

If you need to build the container locally:

```bash
docker build \
  --build-arg HTTP_PROXY=$http_proxy \
  --build-arg HTTPS_PROXY=$https_proxy \
  -t riscvintl/udb:local \
  .devcontainer
```

## Container Features

- Ubuntu 24.04 base image
- Pre-installed development tools (gcc, g++, gdb, etc.)
- RISC-V specific toolchains
- Python packages pre-installed
- Ruby gems pre-installed
- Node.js packages pre-installed
- Proxy-aware configuration
- Non-root user setup

## Troubleshooting

If you encounter issues:

1. Verify your proxy settings if in a corporate environment
2. Try pulling the pre-built image directly: `docker pull riscvintl/udb:latest`
3. Check Docker logs for detailed error messages
4. Ensure you have the latest VS Code and Dev Containers extension
