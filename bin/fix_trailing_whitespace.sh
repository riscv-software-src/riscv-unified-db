#!/bin/bash
# Copyright (c) 2023, RISC-V International
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Script to fix trailing whitespace in common file types
# Used as a fallback when pre-commit is not available
# Enhanced version with better error handling and more file types

set -eo pipefail

echo "Fixing trailing whitespace in files..."

# Find common file types
find_cmd="find . -type f"

# Add file types to check (expanded list with more formats)
file_types=(
  "*.yml"
  "*.yaml"
  "*.rb"
  "*.py"
  "*.c"
  "*.h"
  "*.cpp"
  "*.hpp"
  "*.cc"
  "*.md"
  "*.txt"
  "*.json"
  "*.js"
  "*.adoc"
  "*.gemspec"
  "*.rake"
  "*.idl"
  "*.cmake"
  "*.sh"
  "*.html"
  "*.css"
  "*.scss"
  "Gemfile"
  "Rakefile"
)

# Build the find command with all file types
for i in "${!file_types[@]}"; do
  if [ "$i" -eq 0 ]; then
    find_cmd="$find_cmd -name \"${file_types[$i]}\""
  else
    find_cmd="$find_cmd -o -name \"${file_types[$i]}\""
  fi
done

# Execute the command and remove trailing whitespace
# Adding error handling to prevent failures
echo "Executing: $find_cmd | xargs -I{} sed -i 's/[ \t]*$//' {}"
eval "$find_cmd" | xargs -I{} sed -i 's/[ \t]*$//' {} 2>/dev/null || true

echo "Trailing whitespace removal complete."

# Optional: Report files that were modified
if command -v git >/dev/null 2>&1; then
  echo "Modified files:"
  git diff --name-only | grep -v "^$" || echo "No files were modified"
fi
