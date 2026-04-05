#!/usr/bin/env bash
# Comprehensive deployment script for RenderCart with GPU auto-scaling and Tailscale

set -e

# Parse command-line arguments
WORKERS_ONLY=false
LOCAL_MODE=false

while [ "$#" -gt 0 ]; do
    case "$1" in
        --workers-only|-w)
            WORKERS_ONLY=true
            echo "🔄 Worker-only redeploy mode enabled"
            echo ""
            shift
            ;;
        --local|-l)
            LOCAL_MODE=true
            echo "🏠 Local deployment mode enabled"
            echo "Skipping Tailscale setup and local-only access will be used."
            echo ""
            shift
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "Usage: ./deploy.sh [--workers-only|-w] [--local|-l]"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "RenderCart Deployment Script"
echo "=========================================="
echo ""

# ============================================================================
# PREFLIGHT CHECKS
# ============================================================================
echo "🔍 Running preflight checks..."
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    exit 1
fi

echo "✅ Docker installed"

# Check Docker Compose
if ! docker compose version > /dev/null 2>&1; then
    echo "❌ Docker Compose not found. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker Compose available"

# Check NVIDIA runtime
if ! docker info | grep -q "NVIDIA"; then
    echo "⚠️  NVIDIA Docker runtime not detected. Installing..."
fi

# Validate NVIDIA runtime by executing nvidia-smi inside an NVIDIA container.
if ! docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi > /dev/null 2>&1; then
    echo "❌ NVIDIA container runtime is not working."
    echo "Install NVIDIA Container Toolkit and restart Docker, then try again."
    echo "Guide: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html"
    exit 1
fi

echo "✅ NVIDIA Docker runtime available"

# Check nvidia-smi
if ! command -v nvidia-smi &> /dev/null; then
    echo "❌ nvidia-smi not found. Please install NVIDIA drivers."
    exit 1
fi

echo "✅ nvidia-smi available"

# Verify nvidia-smi works
if ! nvidia-smi > /dev/null 2>&1; then
    echo "❌ nvidia-smi failed. NVIDIA drivers may not be working correctly."
    exit 1
fi

echo "✅ NVIDIA drivers working"
echo ""

# ============================================================================
# TAILSCALE SETUP
# ============================================================================

if [ "$WORKERS_ONLY" = false ] && [ "$LOCAL_MODE" = false ]; then
    echo "🔗 Setting up Tailscale..."
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

# Check Tailscale connection
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
echo "✅ Tailscale connected"
echo "Tailscale IP: $TAILSCALE_IP"
echo ""
fi

# ============================================================================
# GPU DISCOVERY
# ============================================================================
echo "🔍 Discovering GPU hardware..."
echo ""

# Run GPU detection
if ! python detect_gpus.py > docker-compose.workers.yml; then
    echo "❌ GPU detection failed."
    exit 1
fi

echo "✅ GPU discovery complete"
echo ""

# ============================================================================
# WORKER COMPOSE GENERATION
# ============================================================================
echo "📋 Generating worker overlay..."
echo ""

# Verify worker overlay was created
if [ ! -f "docker-compose.workers.yml" ]; then
    echo "❌ Worker overlay file not created."
    exit 1
fi

echo "✅ Worker overlay generated at docker-compose.workers.yml"
echo ""

# ============================================================================
# COMPOSE UP WITH BASE + GENERATED OVERLAY
# ============================================================================
echo "🚀 Deploying services..."
echo ""

# Deploy with Docker Compose
if [ "$WORKERS_ONLY" = true ]; then
    # Worker-only redeploy: recreate only worker containers
    echo "🔄 Redeploying worker containers only..."
    WORKER_SERVICES=$(awk '/^  worker-/{name=$1; sub(/:$/, "", name); print name}' docker-compose.workers.yml | tr '\n' ' ')
    if [ -z "$WORKER_SERVICES" ]; then
        echo "❌ No worker services were generated."
        exit 1
    fi
    docker compose -f docker-compose.yml -f docker-compose.workers.yml up -d --force-recreate $WORKER_SERVICES
    echo "✅ Worker containers redeployed"
else
    # Full deployment
    docker compose -f docker-compose.yml -f docker-compose.workers.yml up -d
    echo "✅ Services deployed"
fi

echo ""

# ============================================================================
# POST-DEPLOY HEALTH CHECKS
# ============================================================================

if [ "$WORKERS_ONLY" = false ]; then
    echo "✅ Running post-deploy health checks..."
    echo ""

# Check API health
MAX_RETRIES=30
RETRY_DELAY=5
API_READY=false

for ((i=1; i<=$MAX_RETRIES; i++)); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        API_READY=true
        break
    fi
    echo "⏳ Waiting for API to be ready ($i/$MAX_RETRIES)..."
    sleep $RETRY_DELAY
    if [ $i -lt $MAX_RETRIES ]; then
        echo "   Retrying in $RETRY_DELAY seconds..."
    fi
done

if [ "$API_READY" = true ]; then
    echo "✅ API is healthy"
else
    echo "⚠️  API health check timed out"
fi

# Check Redis health
REDIS_READY=false
for ((i=1; i<=$MAX_RETRIES; i++)); do
    if docker compose exec redis redis-cli ping > /dev/null 2>&1; then
        REDIS_READY=true
        break
    fi
    echo "⏳ Waiting for Redis to be ready ($i/$MAX_RETRIES)..."
    sleep $RETRY_DELAY
    if [ $i -lt $MAX_RETRIES ]; then
        echo "   Retrying in $RETRY_DELAY seconds..."
    fi
done

if [ "$REDIS_READY" = true ]; then
    echo "✅ Redis is healthy"
else
    echo "⚠️  Redis health check timed out"
fi

# Check Celery workers and queues
CELERY_READY=false
WORKER_SERVICE=$(docker compose -f docker-compose.yml -f docker-compose.workers.yml ps --services | grep '^worker-' | head -n 1 || true)
if [ -z "$WORKER_SERVICE" ]; then
    echo "⚠️  No worker service found for Celery health check"
fi
for ((i=1; i<=$MAX_RETRIES; i++)); do
    if [ -n "$WORKER_SERVICE" ] && docker compose -f docker-compose.yml -f docker-compose.workers.yml exec "$WORKER_SERVICE" celery -A worker inspect ping > /dev/null 2>&1; then
        CELERY_READY=true
        break
    fi
    echo "⏳ Waiting for Celery workers to be ready ($i/$MAX_RETRIES)..."
    sleep $RETRY_DELAY
    if [ $i -lt $MAX_RETRIES ]; then
        echo "   Retrying in $RETRY_DELAY seconds..."
    fi
done

if [ "$CELERY_READY" = true ]; then
    echo "✅ Celery workers are healthy"
    
    # Check queues
    QUEUE_INFO=$(docker compose -f docker-compose.yml -f docker-compose.workers.yml exec "$WORKER_SERVICE" celery -A worker inspect ping 2>/dev/null || echo "")
    if echo "$QUEUE_INFO" | grep -q "ok"; then
        echo "✅ Celery queues are operational"
    else
        echo "⚠️  Could not verify Celery queues"
    fi
else
    echo "⚠️  Celery health check timed out"
fi

fi

echo ""

# ============================================================================
# DEPLOYMENT SUMMARY
# ============================================================================
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
echo ""

# Show running services
echo "Running Services:"
docker compose -f docker-compose.yml -f docker-compose.workers.yml ps --format "table {{.Service}}\t{{.Status}}"
echo ""

if [ "$WORKERS_ONLY" = false ]; then
    echo "API will be accessible at:"
    if [ "$LOCAL_MODE" = true ]; then
        echo "  - http://localhost:8000"
        echo "  - http://$(hostname):8000"
        echo ""
        echo "To access the API locally on this server:"
        echo "  curl http://localhost:8000"
        echo ""
    else
        echo "  - http://$TAILSCALE_IP:8000"
        echo "  - http://$(hostname):8000"
        echo ""
        echo "To access the API from your laptop:"
        echo "  curl http://$TAILSCALE_IP:8000"
        echo ""
    fi
fi

echo "Worker-only redeploy command:"
echo "  ./deploy.sh --workers-only"
echo ""

echo "✅ Deployment complete!"
