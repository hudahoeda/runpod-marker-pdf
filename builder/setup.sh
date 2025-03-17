#!/bin/bash

# Stop script on error
set -e 

# Update System
apt-get update && apt-get upgrade -y 

# Install System Dependencies
apt-get install -y --no-install-recommends \
    software-properties-common \
    curl \
    git \
    openssh-server \
    libgl1 \
    libx11-6 \
    build-essential

# Clean up unnecessary packages and reduce image size
apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/* 