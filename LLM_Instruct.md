# RenderCart LLM Instructions

Use these rules when making changes in this repo.

## Priorities
- Preserve correctness, security, and production safety over speed or cleverness.
- Prefer focused fixes and staged refactors, not rewrites.
- Keep public API routes stable unless a security issue requires a change.

## Backend
- `image-service/api/main.py` should stay thin: app setup, middleware, router registration only.
- Put route logic in `image-service/api/routers/`.
- Put business logic in `image-service/api/services/`.
- Put database query logic in `image-service/api/repositories.py`.
- Keep request/response models in `image-service/api/models.py` and ORM models in `image-service/api/models_db.py`.
- Use UUID-backed string IDs via `image-service/api/ids.py` for `job_id` and `batch_id`.

## Worker
- Keep `image-service/worker/worker.py` as orchestration, not a dumping ground.
- Put status persistence in `image-service/worker/status_store.py`.
- Put uploads/storage handling in `image-service/worker/uploads.py`.
- Put webhook logic in `image-service/worker/webhooks.py`.
- Validate all external URLs with `image-service/url_safety.py`.
- Never trust `image_url` or `callback_url`; reject private/internal targets.

## Security and Config
- Auth should stay enabled by default. Do not set `NO_AUTH=true` except for explicit local-dev workflows.
- Do not add wildcard CORS. Use `CORS_ALLOWED_ORIGINS` from config.
- Prefer config-driven behavior in `image-service/api/config.py`; document new env vars in `.env.example` and `.env.sample`.
- Avoid import-time failures for optional/heavy dependencies when possible.

## Data and Storage
- Persist stable asset storage keys, not only presigned URLs.
- Avoid N+1 query patterns; use eager loading or repository-level aggregation.
- Keep Alembic migrations aligned with ORM changes.

## Frontend
- Centralize API calls in `image-service/ui/src/lib/apiClient.js`.
- Respect the saved API key flow; do not bypass auth in UI code.
- Avoid duplicate fetching on every input change; prefer submit-driven or intentional refresh flows.
- Remove dead props, mocks, and placeholder integrations instead of wiring around them.

## Testing and Quality
- Add or update tests for behavior changes.
- Prefer `pytest` for backend tests and keep frontend checks passing.
- Keep `ruff`, `pytest`, `npm run lint`, `npm run test`, and `npm run build` green when changing relevant areas.
- Do not leave behind one-off validation scripts when proper tests should exist.

## Change Style
- Make minimal, composable edits.
- Do not revert unrelated user changes.
- If a change touches API, worker, schema, and UI behavior together, verify the full flow carefully.
