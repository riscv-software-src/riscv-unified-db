#!/bin/bash

# Install Ruby gems with proper error handling
bundle install --verbose || echo "Warning: bundle install failed"

# Activate virtual environment and install Python packages
if [ -f "requirements.txt" ]; then
  source /opt/venv/bin/activate
  # Ensure pip is installed in the virtual environment
  python -m ensurepip --upgrade || echo "Warning: ensurepip failed"
  pip install -r requirements.txt || echo "Warning: pip install failed"
fi