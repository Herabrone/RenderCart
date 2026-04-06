FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/cache/huggingface

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY logging_config.py ./
COPY worker/ ./

CMD ["celery", "-A", "worker", "worker", "--loglevel=info", "--concurrency=1"]