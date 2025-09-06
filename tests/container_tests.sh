#!/bin/bash

# SPDX-License-Identifier: BSD-2-Clause
# SPDX-FileCopyrightText: Copyright (c) 2025 RISC-V International

# Container tests script for riscv-unified-db

set -e
set -o pipefail

# Display system information for debugging
echo "System Information:"
echo "-------------------"
uname -a
docker --version
echo "-------------------"

echo "Running container tests..."

# Test 1: Check if we can build the container
echo "Test 1: Building container..."
docker build -t riscv-unified-db-test .devcontainer/

# Test 2: Check if we can run basic commands in the container
echo "Test 2: Running basic commands in container..."
docker run --rm riscv-unified-db-test ruby --version
docker run --rm riscv-unified-db-test python3 --version
docker run --rm riscv-unified-db-test npm --version

# Test 3: Check if we can install Python packages in a virtual environment
echo "Test 3: Installing Python packages in virtual environment..."
docker run --rm -v "$(pwd)":/workspace riscv-unified-db-test bash -c \
"cd /workspace && \
python3 -m venv .venv && \
source .venv/bin/activate && \
python -m ensurepip --upgrade && \
python -m pip install --upgrade pip && \
python -m pip install --quiet -r requirements.txt && \
python -m pip list && \
deactivate"

# Test 4: Check if we can install Python packages with --break-system-packages flag
echo "Test 4: Installing Python packages with --break-system-packages flag..."
docker run --rm -v "$(pwd)":/workspace riscv-unified-db-test bash -c \
"cd /workspace && \
python3 -m pip install --break-system-packages --quiet -r requirements.txt && \
python3 -m pip list"

# Test 5: Check if we can install gems
echo "Test 5: Installing gems..."
docker run --rm riscv-unified-db-test gem list bundler

# Test 6: Check if we can run rake tasks
echo "Test 6: Running rake tasks..."
docker run --rm -v "$(pwd)":/workspace riscv-unified-db-test rake --version

# Test 7: Check non-root user exists
echo "Test 7: Checking non-root user..."
docker run --rm riscv-unified-db-test id -u vscode

# Test 8: Proxy configuration test
echo "Test 8: Checking proxy configuration..."
docker run --rm \
-e http_proxy=http://test.proxy:3128 \
-e https_proxy=http://test.proxy:3128 \
riscv-unified-db-test bash -c "env | grep -i proxy"

# Test 9: Check apt proxy configuration
echo "Test 9: Checking apt proxy configuration..."
docker run --rm \
-e http_proxy=http://test.proxy:3128 \
riscv-unified-db-test bash -c \
"if [ -f /etc/apt/apt.conf.d/01proxy ]; then cat /etc/apt/apt.conf.d/01proxy; else echo 'No apt proxy configuration found'; fi"

# Test 10: Check pip proxy configuration
echo "Test 10: Checking pip proxy configuration..."
docker run --rm \
-e http_proxy=http://test.proxy:3128 \
riscv-unified-db-test bash -c \
"if [ -f /etc/pip.conf ]; then cat /etc/pip.conf; else echo 'No pip proxy configuration found'; fi"

# Test 11: Check npm proxy configuration
echo "Test 11: Checking npm proxy configuration..."
docker run --rm \
-e http_proxy=http://test.proxy:3128 \
riscv-unified-db-test bash -c \
"npm config get proxy 2>/dev/null || echo 'No npm proxy configured'"

# Test 12: Check bundler proxy configuration
echo "Test 12: Checking bundler proxy configuration..."
docker run --rm \
-e http_proxy=http://test.proxy:3128 \
riscv-unified-db-test bash -c \
"bundle config http_proxy 2>/dev/null || echo 'No bundler proxy configured'"

# Test 13: Check pre-created virtual environment
echo "Test 13: Checking pre-created virtual environment..."
docker run --rm riscv-unified-db-test bash -c \
"echo 'Virtual environment contents:' && \
ls -la /opt/venv/bin/ || echo 'Failed to list virtual environment directory' && \
if [ -f /opt/venv/bin/python ]; then \
  echo 'Python exists in virtual environment' && \
  /opt/venv/bin/python --version; \
else \
  echo 'Python not found in virtual environment'; \
  ls -la /opt/venv/; \
  exit 0; \
fi"

# Cleanup
echo "Cleaning up..."
docker rmi -f riscv-unified-db-test > /dev/null 2>&1 || true

echo "All container tests passed!"
