#!/bin/bash

# Build the image with Podman
podman build -t validator-ui .

# Stop any existing container
podman stop validator-ui

# Remove the stopped container
podman rm validator-ui

# Run the container in detached mode
podman run -d -p 8050:8050 --name validator-ui validator-ui

# Check running containers
podman ps

# View logs
podman logs validator-ui