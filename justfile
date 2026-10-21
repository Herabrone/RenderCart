set shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

dev:
    docker compose -f infra/compose.yml -f infra/compose.dev.yml up --build

test:
    cd backend; uv run pytest
    cd apps/web; pnpm test

lint:
    cd backend; uv run ruff check .
    cd apps/web; pnpm lint

fmt:
    cd backend; uv run ruff format .
    cd apps/web; pnpm format

migrate:
    cd backend; uv run alembic upgrade head

gen-api:
    pnpm --dir apps/web gen:api
