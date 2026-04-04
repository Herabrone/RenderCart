#!/usr/bin/env bash
# Comprehensive deployment script for RenderCart with GPU auto-scaling and Tailscale

set -e

echo "=========================================="
echo "RenderCart Deployment Script"
echo "=========================================="
echo ""

# Check if Tailscale is installed
if ! command -v tailscale &> /dev/null; then
    echo "Tailscale not found. Installing..."
    curl -fsSL https://tailscale.com/install.sh | sh
    echo "Tailscale installed. Please log in:"
    tailscale up --login-server=https://controlplane.tailscale.com
    echo ""
    echo "After logging in, run this script again."
    exit 1
fi

# Check if logged in to Tailscale
if ! tailscale status &> /dev/null; then
    echo "Not logged in to Tailscale. Logging in..."
    tailscale up --login-server=https://controlplane.tailscale.com
    echo ""
    echo "Logged in to Tailscale. Run this script again to continue deployment."
    exit 1
fi

echo "Checking Tailscale connection..."
TAILSCALE_IP=$(tailscale ip -4)
if [ -z "$TAILSCALE_IP" ]; then
    echo "Tailscale not connected. Starting Tailscale..."
    tailscale up
    TAILSCALE_IP=$(tailscale ip -4)
    if [ -z "$TAILSCALE_IP" ]; then
        echo "Failed to connect to Tailscale."
        exit 1
    fi
fi
echo "Tailscale IP: $TAILSCALE_IP"
echo ""

# Generate worker overlay from detected GPU hardware
echo "Generating worker overlay from GPU hardware..."
python detect_gpus.py > docker-compose.workers.yml

echo ""
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
echo "API will be accessible at:"
echo "  - http://$TAILSCALE_IP:8000"
echo "  - http://$(hostname):8000"
echo ""
echo "To deploy, run:"
echo "  docker compose -f docker-compose.yml -f docker-compose.workers.yml up -d"
echo ""
echo "To access the API from your laptop:"
echo "  curl http://$TAILSCALE_IP:8000"
echo ""
