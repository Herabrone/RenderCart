FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/cache/huggingface

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY configs ./configs
COPY worker ./worker
COPY business_presets.py ./
COPY config.py ./
COPY detect_gpus.py ./
COPY logging_config.py ./
COPY model_loader.py ./
COPY task_queue.py ./
COPY url_safety.py ./

CMD ["celery", "-A", "worker.worker", "worker", "--loglevel=info", "--concurrency=1"]
