#!/bin/bash

# Checks if pre-commit is installed and available
if command -v pre-commit &>/dev/null; then
  echo "Using pre-commit to fix trailing whitespace"
  pre-commit run trailing-whitespace --all-files
  exit_code=$?
  if [ $exit_code -ne 0 ]; then
    echo "Warning: pre-commit found and fixed trailing whitespace"
    # Stage the changes
    git add .
  else
    echo "No trailing whitespace issues found by pre-commit"
  fi
else
  echo "pre-commit not found, using direct sed approach"
  
  # Fix with sed (POSIX compatible)
  # Loop through file types to avoid command line length limits
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

  for type in "${file_types[@]}"; do
    echo "Processing files of type: $type"
    find . -name "$type" -type f -exec sed -i 's/[ \t]*$//' {} \; 2>/dev/null || echo "Error processing $type files"
  done

  # Stage any changes
  git add .
fi

# Check if any files were modified
if git diff --cached --quiet; then
  echo "No files were modified"
else
  echo "Files were modified to fix trailing whitespace"
  # List modified files
  git diff --cached --name-only
fi
