#!/bin/bash

npm i
bundle install --verbose

# Install Python packages with --break-system-packages flag to avoid PEP 668 error
pip3 install --break-system-packages -r requirements.txt 2>/dev/null || echo "No requirements.txt file found"
