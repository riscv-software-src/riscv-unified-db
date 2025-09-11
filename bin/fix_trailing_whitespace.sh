#!/bin/bash
# Copyright (c) 2023, RISC-V International
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Enhanced script to fix trailing whitespace in common file types
# Used as a fallback when pre-commit is not available
# Comprehensive version with extra file types and improved error handling

set -eo pipefail

echo "Starting comprehensive trailing whitespace cleanup..."

# Create a temporary directory for any necessary backup files
mkdir -p /tmp/whitespace_fix_backups

# Exclude directories that shouldn't be modified
exclude_dirs=(
  ".git"
  "node_modules"
  ".singularity"
  ".home"
  "build"
)

# Build the exclusion arguments
exclude_args=""
for dir in "${exclude_dirs[@]}"; do
  exclude_args="$exclude_args -not -path \"./$dir/*\""
done

# Define a comprehensive list of file types to check
file_types=(
  # YAML files
  "*.yml" "*.yaml"
  # Ruby files
  "*.rb" "*.gemspec" "*.rake" "Gemfile" "Rakefile"
  # Python files
  "*.py"
  # C/C++ files
  "*.c" "*.h" "*.cpp" "*.hpp" "*.cc"
  # Documentation files
  "*.md" "*.txt" "*.adoc" "*.rst"
  # Web files
  "*.html" "*.css" "*.scss" "*.js" "*.ts" "*.json"
  # Build files
  "*.cmake" "CMakeLists.txt" "Makefile" "makefile"
  # Shell scripts
  "*.sh" "*.bash"
  # Other
  "*.idl" "*.toml" "*.xml"
)

# Build the find command with all file types
find_cmd="find . -type f"
for i in "${!file_types[@]}"; do
  if [ "$i" -eq 0 ]; then
    find_cmd="$find_cmd \\( -name \"${file_types[$i]}\""
  else
    find_cmd="$find_cmd -o -name \"${file_types[$i]}\""
  fi
done
find_cmd="$find_cmd \\)"

# Add exclusion arguments
for dir in "${exclude_dirs[@]}"; do
  find_cmd="$find_cmd -not -path \"./$dir/*\""
done

# Print the command for debugging
echo "Generated find command: $find_cmd"

# Execute the command and remove trailing whitespace
echo "Executing whitespace cleanup..."
eval "$find_cmd" | while read -r file; do
  # Skip binary files and non-text files
  if file "$file" | grep -q "text"; then
    # Make a backup just in case
    cp "$file" "/tmp/whitespace_fix_backups/$(basename "$file").bak" 2>/dev/null || true
    
    # Remove trailing whitespace
    sed -i 's/[ \t]*$//' "$file" 2>/dev/null || {
      echo "Warning: Failed to clean whitespace in $file, skipping"
    }
    
    # Also fix line endings if they're mixed (convert CRLF to LF)
    if grep -q $'\r' "$file"; then
      echo "Converting CRLF to LF in $file"
      sed -i 's/\r$//' "$file" 2>/dev/null || true
    fi
  else
    echo "Skipping likely binary file: $file"
  fi
done

echo "Trailing whitespace removal complete."

# Report files that were modified
if command -v git >/dev/null 2>&1; then
  echo "Modified files:"
  git diff --name-only | grep -v "^$" || echo "No files were modified"
fi

echo "Whitespace cleanup finished successfully."
