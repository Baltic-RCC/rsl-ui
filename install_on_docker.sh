#!/bin/bash

# Build the image with Docker
docker build -t validator-ui .

# Stop any existing container
docker stop validator-ui

# Remove the stopped container
docker rm validator-ui

# Run the container in detached mode
docker run -d -p 8050:8050 --name validator-ui validator-ui

# Check running containers
docker ps

# View logs
docker logs validator-ui