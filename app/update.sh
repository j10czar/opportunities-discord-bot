#!/bin/bash

set -e  # ❗ Exit immediately if a command fails
set -o pipefail  # ❗ Fail if any part of a pipe fails

echo "Pulling latest code from GitHub..."
git fetch origin main
git reset --hard origin/main

echo "Rebuilding and restarting container..."
# Step 1: Build the updated image
docker-compose build

# Step 2: Stop and remove old containers cleanly
docker-compose down --remove-orphans

# Step 3: Recreate containers fresh from the new image
docker-compose up -d --force-recreate

echo "✅ Hotfix pulled and container updated successfully!"

