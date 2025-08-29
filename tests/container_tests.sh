#!/bin/bash

# SPDX-License-Identifier: BSD-2-Clause
# SPDX-FileCopyrightText: Copyright (c) 2025 RISC-V International

# Container tests script for riscv-unified-db

set -e

echo "Running container tests..."

# Test 1: Check if we can build the container
echo "Test 1: Building container..."
docker build -t riscv-unified-db-test .devcontainer/

# Test 2: Check if we can run basic commands in the container
echo "Test 2: Running basic commands in container..."
docker run --rm riscv-unified-db-test ruby --version
docker run --rm riscv-unified-db-test python3 --version
docker run --rm riscv-unified-db-test npm --version

# Test 3: Check if we can install Python packages
echo "Test 3: Installing Python packages..."
docker run --rm -v $(pwd):/workspace riscv-unified-db-test pip3 install --break-system-packages -r /workspace/requirements.txt

# Test 4: Check if we can install gems
echo "Test 4: Installing gems..."
docker run --rm riscv-unified-db-test gem list bundler

# Test 5: Check if we can run rake tasks
echo "Test 5: Running rake tasks..."
docker run --rm -v $(pwd):/workspace riscv-unified-db-test rake --version

# Test 6: Check non-root user exists
echo "Test 6: Checking non-root user..."
docker run --rm riscv-unified-db-test id -u vscode

# Test 7: Proxy configuration test
echo "Test 7: Checking proxy configuration..."
if [ -n "$http_proxy" ] || [ -n "$https_proxy" ]; then
    echo "Proxy is configured: HTTP_PROXY=$http_proxy, HTTPS_PROXY=$https_proxy"
    # Test proxy connectivity if configured
    docker run --rm -e http_proxy -e https_proxy riscv-unified-db-test env | grep -i proxy
else
    echo "No proxy configured"
fi

echo "All container tests passed!"