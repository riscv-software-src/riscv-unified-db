# SPDX-License-Identifier: BSD-2-Clause
# SPDX-FileCopyrightText: Copyright (c) 2025 RISC-V International

# Container Testing Guide

This document describes how to test the development container functionality, especially in environments with proxy requirements.

## Prerequisites

- Docker installed
- VS Code with Remote Containers extension
- Access to proxy settings (if testing in corporate environment)

## Running Tests

1. Basic Test:
```bash
./tests/container_tests.sh
```

2. With Proxy:
```bash
export http_proxy="your-proxy-url"
export https_proxy="your-proxy-url"
./tests/container_tests.sh
```

## Test Cases

### 1. Build Tests
- Container builds without proxy
- Container builds with proxy
- All dependencies are pre-installed

### 2. Package Manager Tests
- APT works through proxy
- Pip works through proxy
- NPM works through proxy
- Bundle works through proxy

### 3. Security Tests
- Non-root user exists and works
- Permissions are correct
- Proxy configurations are secure

### 4. Integration Tests
- VS Code can connect
- Docker Compose works
- Volume mounts work

## Troubleshooting

### Common Issues

1. Proxy Connection Failed
```bash
# Check proxy settings
env | grep -i proxy
# Try with explicit proxy
docker build --build-arg HTTP_PROXY=... .
```

2. Package Installation Failed
```bash
# Check package manager configs
docker run --rm container-name apt-get update
docker run --rm container-name pip config list
```

3. Permission Issues
```bash
# Check user setup
docker run --rm container-name id vscode
# Check workspace permissions
docker run --rm container-name ls -la /workspace
```

## Adding New Tests

To add new test cases:
1. Add test function to container_tests.sh
2. Update GitHub Actions workflow if needed
3. Update documentation

## CI/CD Integration

The tests are automatically run:
- On pull requests affecting container files
- On pushes to main branch
- Can be run manually via GitHub Actions
