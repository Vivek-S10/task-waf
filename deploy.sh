#!/bin/bash
set -e

echo "======================================"
echo "    Deploying Agent WAF to AWS EC2    "
echo "======================================"

echo "[1/3] Pulling latest code..."
git pull origin main || echo "Not a git repository or no upstream found. Assuming code is already present."

echo "[2/3] Rebuilding Docker Containers..."
# Force recreation and rebuild, dropping old dangling images
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml down

echo "[3/3] Starting Services..."
docker compose -f docker-compose.prod.yml up -d

echo "Cleaning up dangling images to free up space..."
docker image prune -f

echo "======================================"
echo " Deployment Complete! WAF is running. "
echo " View logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "======================================"
