#!/bin/bash
# SPDX-License-Identifier: BSD-2-Clause
# SPDX-FileCopyrightText: Copyright (c) 2025 RISC-V International

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Test results counter
PASSED=0
FAILED=0

# Helper function for testing
test_case() {
    local name=$1
    local cmd=$2
    echo "Testing: $name"
    if eval "$cmd"; then
        echo -e "${GREEN}✓ Passed: $name${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗ Failed: $name${NC}"
        ((FAILED++))
    fi
    echo "----------------------------------------"
}

# 1. Basic Container Build Tests
echo "=== Basic Container Build Tests ==="
test_case "Build without proxy" "docker build -t riscv-udb-test:no-proxy .devcontainer/"
test_case "Build with proxy" "docker build --build-arg HTTP_PROXY=\"$http_proxy\" --build-arg HTTPS_PROXY=\"$https_proxy\" -t riscv-udb-test:with-proxy .devcontainer/"

# 2. Package Manager Tests
echo "=== Package Manager Tests ==="

# 2.1 APT
test_case "APT Update" "docker run --rm riscv-udb-test:with-proxy apt-get update"
test_case "APT Install" "docker run --rm riscv-udb-test:with-proxy apt-get install -y curl"

# 2.2 Python/pip
test_case "Pip Install" "docker run --rm riscv-udb-test:with-proxy python3 -m pip install --no-cache-dir requests"
test_case "Python Requirements" "docker run --rm riscv-udb-test:with-proxy python3 -m pip freeze | grep -f requirements.txt"

# 2.3 Node.js/npm
test_case "NPM Install" "docker run --rm riscv-udb-test:with-proxy npm install -g typescript"
test_case "Node Modules" "docker run --rm riscv-udb-test:with-proxy test -d node_modules"

# 2.4 Ruby/Bundler
test_case "Bundle Install" "docker run --rm riscv-udb-test:with-proxy bundle install"
test_case "Gem List" "docker run --rm riscv-udb-test:with-proxy bundle list | grep -f Gemfile"

# 3. User and Permission Tests
echo "=== Security Tests ==="
test_case "Non-root user exists" "docker run --rm riscv-udb-test:with-proxy id vscode"
test_case "Workspace permissions" "docker run --rm riscv-udb-test:with-proxy test -w /workspace"

# 4. Proxy Configuration Tests
echo "=== Proxy Configuration Tests ==="
test_case "APT proxy config" "docker run --rm riscv-udb-test:with-proxy cat /etc/apt/apt.conf.d/proxy.conf"
test_case "Pip proxy config" "docker run --rm riscv-udb-test:with-proxy python3 -m pip config list | grep proxy"
test_case "NPM proxy config" "docker run --rm riscv-udb-test:with-proxy npm config get proxy"
test_case "Bundle proxy config" "docker run --rm riscv-udb-test:with-proxy bundle config get proxy"

# Print summary
echo "=== Test Summary ==="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo "Total: $((PASSED + FAILED))"

# Exit with failure if any tests failed
[ $FAILED -eq 0 ]
