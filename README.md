# RenderCart

RenderCart is a freemium utility-tools platform. The product and implementation handoff is in [docs/PLAN.md](docs/PLAN.md); read it before making product or architecture changes.

## Local development

Prerequisites: Docker Desktop with the Linux engine running, Node.js LTS, pnpm, Python 3.12+, and `uv`. `just` is the task runner; each recipe has a direct command shown below.

1. Copy `.env.example` to `.env` and adjust local secrets if needed.
2. Run `just dev` (or `docker compose -f infra/compose.yml -f infra/compose.dev.yml up --build`).
3. Open <http://localhost>. FastAPI health is available at <http://localhost/api/health>.
4. Mailpit is at <http://localhost:8025>; MinIO console is at <http://localhost:9001>.

The local profile defaults to `AI_MODE=mock` and does not require external credentials. Stripe CLI is optional and enabled with `--profile stripe` after setting a test API key.

The current reference server tools are **Merge PDF** and **Image Converter**. Their browser flow obtains a signed MinIO upload URL, uploads directly to object storage, creates a queued job, and polls the job page for completion. The directory also includes five browser-only tools: Word Counter, JSON Formatter, static QR, Base64, and Password Generator. These tools work without a GPU. Configure `S3_ENDPOINT`, `S3_PUBLIC_ENDPOINT`, and `S3_PROXY_SITE` for your internal storage address, public URL, and Caddy route; configure `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` before accepting guest traffic in production.

To bootstrap the owner after creating and verifying the account, run `uv run --project backend rendercart admin promote owner@example.com --role super_admin` with `SUPER_ADMIN_EMAIL` set to the same address. The command refuses to grant `super_admin` to any other email. Staff access requires TOTP enrollment. Credit grants for development can be recorded with `uv run --project backend rendercart credits grant user@example.com 100 --reason "development allocation"`.

The price page currently documents the planned $9.99 monthly Pro plan and $2.99 day pass; checkout and paid entitlements are part of Phase 2 and are not active yet.

## Common commands

- `just dev` — start the local stack.
- `just test` — run backend and frontend checks.
- `just lint` / `just fmt` — lint or format source.
- `just migrate` — apply database migrations.
- `just gen-api` — regenerate the TypeScript API client from FastAPI OpenAPI.

See [docs/runbooks](docs/runbooks/) for operational procedures. Never use the example credentials in production.
