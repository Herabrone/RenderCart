#!/usr/bin/env bash
# Generate worker overlay from detected GPU hardware

set -e

echo "Generating worker overlay from GPU hardware..."

# Generate worker services using Python script
WORKER_SERVICES=$(python detect_gpus.py)

# Create worker overlay file
cat <<EOF > docker-compose.workers.yml
$WORKER_SERVICES
EOF

echo "Worker overlay generated at docker-compose.workers.yml"
echo ""
echo "To deploy, run:"
echo "  docker compose -f docker-compose.yml -f docker-compose.workers.yml up -d"

echo ""
echo "✅ Worker overlay generation complete!"
