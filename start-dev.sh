#!/bin/bash

# SPDX-License-Identifier: BSD-2-Clause
# SPDX-FileCopyrightText: Copyright (c) 2025 RISC-V International

# Start development environment script

# Set script to be executable
chmod +x "$0"

set -e

echo "Starting development environment..."

# Check if docker-compose exists
if ! command -v docker-compose &> /dev/null; then
    echo "docker-compose is not installed. Please install Docker Desktop or Docker Compose."
    exit 1
fi

# Bring up the development environment
docker-compose up -d

echo "Development environment started!"
echo "Use 'docker-compose exec dev bash' to enter the container."