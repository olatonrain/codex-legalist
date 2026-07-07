#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  deploy-docker.sh  —  Codex Legalis Docker Deployment Script
# ─────────────────────────────────────────────────────────────────
set -e

echo "=> Fetching latest changes from Git..."
git fetch --all
git reset --hard origin/main

echo "=> Building Docker image..."
docker build --no-cache -t codex-legalis .

echo "=> Stopping and removing old container (if exists)..."
docker rm -f legalis_app || true

echo "=> Starting new Docker container on port 8000..."
docker run -d --name legalis_app -p 8000:8000 --restart unless-stopped codex-legalis

echo ""
echo "✅ Deployment complete! The app is running on port 8000."
echo "   Run 'docker logs -f legalis_app' to view live logs."
