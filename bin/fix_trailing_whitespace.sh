#!/bin/bash

# Script to fix trailing whitespace in common file types
# Used as a fallback when pre-commit is not available

echo "Fixing trailing whitespace in files..."

# Find common file types
find_cmd="find . -type f"

# Add file types to check
file_types=(
  "*.yml"
  "*.yaml"
  "*.rb"
  "*.py"
  "*.c"
  "*.h"
  "*.cpp"
  "*.md"
  "*.txt"
  "*.json"
  "*.js"
  "*.adoc"
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
eval "$find_cmd" | xargs -I{} sed -i 's/[ \t]*$//' {}

echo "Trailing whitespace removal complete."
