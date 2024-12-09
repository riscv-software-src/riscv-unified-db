# Use Ubuntu 24.04 as base image
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DEVCONTAINER_ENV=1
ENV BUNDLE_PATH=/usr/local/bundle
ENV BUNDLE_APP_CONFIG=/usr/local/bundle

# Set working directory
WORKDIR /workspace

COPY Gemfile Gemfile.lock ./

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    gh \
    less \
    python3 \
    python3.12-venv \
    python3-pip \
    build-essential \
    ruby \
    ruby-dev \
    bundler \
    nodejs \
    npm \
    ditaa && \
    bundle install && \
    apt-get clean autoclean && \
    apt-get autoremove -y && \
    rm -rf /var/lib/{apt,dpkg,cache,log}/*

COPY package.json package-lock.json ./

# Stay in workspace directory
WORKDIR /workspace