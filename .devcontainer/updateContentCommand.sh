#!/bin/bash

bundle install --verbose

# Install Python packages with --break-system-packages flag to avoid PEP 668 error
pip3 install --break-system-packages -r requirements.txt
