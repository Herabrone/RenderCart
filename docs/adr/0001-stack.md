# ADR 0001: RenderCart platform stack

- Status: accepted
- Date: 2026-10-17
- Decision owners: RenderCart owner

## Context

RenderCart is pivoting from a Shopify image service to a freemium utility-tools platform. The system must support SEO pages, file processing, GPU-backed AI jobs, billing, and strict isolation of restricted tools.

## Decision

Use Next.js App Router with TypeScript, Tailwind and shadcn/ui; FastAPI with Pydantic v2, SQLAlchemy and Alembic; Redis and Celery with separate CPU/GPU queues; PostgreSQL with pgvector; MinIO-compatible object storage; the owner's GPU servers as primary AI infrastructure with OpenRouter fallback for LLM tasks only; Docker Compose on a VPS; Stripe billing; and email/password, Google, GitHub, and magic-link sign-in. Preserve the ordered access levels and super-admin-only Vault described in `docs/PLAN.md`.

## Consequences

The repository is a pnpm/uv monorepo. Server-side tools execute through background jobs, while client tools run in the browser. The API is the authorization boundary. Local development must support mock AI and must not require external credentials.
