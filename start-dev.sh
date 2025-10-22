#!/bin/bash
# Development environment setup script

# Load proxy settings if they exist
if [ -f ~/.proxy_config ]; then
    source ~/.proxy_config
fi

# Set default proxy if not set
if [ -z "$http_proxy" ]; then
    echo "No proxy settings found. If you need proxy, set http_proxy and https_proxy environment variables."
fi

# Start the development container
docker compose up -d
