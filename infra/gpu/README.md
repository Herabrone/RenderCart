# GPU server deployment

The GPU host connects to the VPS over the owner's private Tailscale or WireGuard network. Do not publish the vLLM port on a public interface. The compose file uses host networking so the worker can reach the VPS services over the private tunnel and vLLM can bind to the host's private interface; restrict TCP 8000 and Redis/Postgres/S3 access with the host firewall to the tailnet peers.

## Configure

1. Install Docker Engine with NVIDIA Container Toolkit on a Linux GPU host. Verify the host can run a GPU-enabled container before starting this stack.
2. Create `infra/gpu/.env.gpu` with the environment needed by the worker: `DATABASE_URL`, `REDIS_URL` (the Celery broker DB), `S3_ENDPOINT`, `S3_PUBLIC_ENDPOINT`, storage credentials and bucket names, `SECRET_KEY`, `ENCRYPTION_KEY`, `APP_ENV`, `AI_MODE=remote`, `AI_LOCAL_BASE_URL=http://127.0.0.1:8000/v1`, `AI_LOCAL_EMBEDDING_BASE_URL=http://127.0.0.1:8001/v1`, `AI_LOCAL_API_KEY`, `AI_LOCAL_CHAT_MODEL`, and `AI_LOCAL_EMBEDDING_MODEL=BAAI/bge-m3`.
3. Create a root-only `.env` in this directory with `VLLM_MODEL`, `VLLM_API_KEY`, optional `HF_TOKEN`, and `VLLM_IMAGE`. Choose model weights only after checking their commercial-use license and fit against the host's available VRAM.
4. From this directory, start with `docker compose --env-file .env -f compose.gpu.yml up -d --build`.
5. On the VPS, configure the same local-provider model and API-key settings. Set `AI_MODE=remote`; use the GPU host's Tailscale/WireGuard address with port 8000 for `AI_LOCAL_BASE_URL` and port 8001 for `AI_LOCAL_EMBEDDING_BASE_URL`. Keep `OPENROUTER_API_KEY` only on the VPS API/worker environment that needs text fallback.
6. Verify `GET /v1/models` and a chat completion from port 8000, and `POST /v1/embeddings` using BGE-M3 from port 8001 over the private interface. The embedding response must contain 1024 values per input. Then stop the chat vLLM service and confirm an LLM request falls back to OpenRouter. Image/audio/embedding jobs have no external fallback and fail cleanly when their required GPU service is unavailable.

The Compose stack runs separate OpenAI-compatible vLLM services for chat completions (port 8000) and BGE-M3 dense embeddings (port 8001). Both use the same GPU device set and API key by default; if the host cannot fit both models in VRAM, move the embedding service to another GPU host and point `AI_LOCAL_EMBEDDING_BASE_URL` at it. `VLLM_MODEL` for chat is intentionally unset because the owner's GPU model/VRAM and commercial model license have not been specified. Replace the sample image tag after reviewing upstream release compatibility with the server's CUDA driver.

## Operations

- Keep model weights and vLLM compile artifacts in the named cache volumes.
- The GPU worker uses one Celery process per GPU queue host and concurrency 1 as a safe baseline. Tune only after observing model VRAM and task concurrency.
- Rotate `VLLM_API_KEY` and update the VPS configuration together. Do not commit `.env.gpu` or model tokens.
- `/api/admin/gpu` reports Celery GPU worker presence and per-queue backlog to staff with verified MFA. To add hardware readings, deploy NVIDIA DCGM Exporter on this GPU host, bind it only to the private Tailscale/WireGuard interface, firewall it to the VPS peer, and set `GPU_METRICS_URL` on the API to that private `/metrics` endpoint. The API parses GPU utilization, memory, temperature, and power readings. Never publish the exporter endpoint to the public internet.
