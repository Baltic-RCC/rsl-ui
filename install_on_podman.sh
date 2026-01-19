#!/bin/bash

# Build the image with Podman using docker format to support HEALTHCHECK
podman build --format docker -t rsl-ui:0.1.6 .

# Stop any existing container
podman stop validator-ui || true

# Remove the stopped container
podman rm validator-ui || true

# Run the container in detached mode
podman run -d -p 8050:8050 --name validator-ui rsl-ui:0.1.6

# Check running containers
podman ps

# View logs
podman logs validator-ui
