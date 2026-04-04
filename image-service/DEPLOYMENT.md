# RenderCart - DevOps-First GPU Auto-Scaling

## Overview

This deployment uses a DevOps-first approach with GPU auto-scaling and Tailscale for secure remote access. The system automatically detects available GPU hardware and generates the appropriate worker topology at deploy time.

## Deployment Architecture

### Core Services (Static)
- **API**: FastAPI service on port 8000
- **Redis**: Message broker and result backend

### Worker Services (Auto-Generated)
- **worker-main-X**: High-end GPUs (1 per service)
- **worker-light**: Lower-end GPUs (multiple per service)
- **worker-preprocess**: Dedicated preprocessing GPU

## Deployment Process

### Prerequisites

1. **Tailscale**: Install Tailscale for secure remote access
2. **Docker**: Docker and Docker Compose installed
3. **NVIDIA Drivers**: NVIDIA GPU drivers with CUDA support

### Quick Start

```bash
# Run the deployment script (installs Tailscale if needed)
./deploy.sh

# Or manually:
# 1. Generate worker overlay from detected GPUs
./generate_workers.sh

# 2. Deploy with Docker Compose
docker compose -f docker-compose.yml -f docker-compose.workers.yml up -d
```

### Manual Deployment Steps

1. **Generate Worker Overlay**
   ```bash
   python detect_gpus.py > docker-compose.workers.yml
   ```
   This script:
   - Detects available NVIDIA GPUs using `nvidia-smi`
   - Categorizes GPUs by capability (main/light/preprocess)
   - Generates appropriate Docker Compose services

2. **Deploy Services**
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.workers.yml up -d
   ```

3. **Access API via Tailscale**
   ```bash
   # Get your Tailscale IP
   TAILSCALE_IP=$(tailscale ip -4)
   
   # Access API
   curl http://$TAILSCALE_IP:8000
   ```

## GPU Detection Logic

The `detect_gpus.py` script categorizes GPUs based on their model:

- **Main GPUs**: High-end models (RTX 3060/70/80/90, 40xx series, A100, A5000)
- **Light GPUs**: Mid-range models (RTX 1660, 2060/70/80, 3050, 4050)
- **Preprocess GPUs**: All other models

## Tailscale Integration

The deployment script automatically:
1. Installs Tailscale if not present
2. Logs in to Tailscale (if needed)
3. Starts Tailscale connection
4. Displays the Tailscale IP for API access

### Accessing from Your Laptop

After deployment, access the API from your laptop via:
```bash
curl http://<tailscale-ip>:8000
```

## Scaling Scenarios

### Single GPU (1x RTX 3060)
```yaml
services:
  worker-main-1:  # Uses GPU 0
```

### Mixed Multi-GPU (2x RTX 3060 + 1x RTX 2060 + 1x GTX 1660)
```yaml
services:
  worker-main-1:  # Uses GPU 0
  worker-main-2:  # Uses GPU 1
  worker-light:   # Uses GPU 2
  worker-preprocess:  # Uses GPU 3
```

### Multi-GPU Rig (4x RTX 3090)
```yaml
services:
  worker-main-1:  # Uses GPU 0
  worker-main-2:  # Uses GPU 1
  worker-main-3:  # Uses GPU 2
  worker-main-4:  # Uses GPU 3
```

## Environment Variables

Required environment variables (set in `.env` file):

```bash
R2_ENDPOINT=https://your-endpoint.r2.cloudflared.com
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=your-bucket
```

## Monitoring and Maintenance

### View Running Services
```bash
docker compose -f docker-compose.yml -f docker-compose.workers.yml ps
```

### View Logs
```bash
# API logs
docker compose logs -f api

# Worker logs
docker compose logs -f worker-main-1
```

### Stop Services
```bash
docker compose -f docker-compose.yml -f docker-compose.workers.yml down
```

### Rebuild Workers
```bash
# Regenerate worker overlay (detects new GPUs)
python detect_gpus.py > docker-compose.workers.yml

# Recreate worker containers
docker compose -f docker-compose.yml -f docker-compose.workers.yml up -d --force-recreate
```

## Future Integration

This deployment is designed for future Stockman integration:
- API remains stable on port 8000
- Worker topology auto-adapts to hardware
- Tailscale provides secure remote access

## Troubleshooting

### No GPUs Detected
```bash
# Check if nvidia-smi is available
nvidia-smi

# Install NVIDIA drivers if needed
```

### Tailscale Connection Issues
```bash
# Check Tailscale status
tailscale status

# Restart Tailscale
tailscale down
tailscale up
```

### Docker Compose Errors
```bash
# Check Docker is running
docker info

# Check compose syntax
docker compose config
```

## Development Notes

- The base `docker-compose.yml` contains only static services (API, Redis)
- Worker services are generated at deploy time based on detected hardware
- This approach allows the same deployment flow from 1x GPU to multi-GPU rigs
- Tailscale ensures secure access without exposing ports on the local network
