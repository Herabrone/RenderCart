# Production host and automatic deployment

This runbook deploys the utility-tools app from `main` to the owner's Ubuntu
machine using a GitHub Actions self-hosted runner. The runner is labelled
`rendercart`; only pushes to `main` trigger production deployment. The site
stack and its persistent Docker volumes stay on the host. Cloudflare Tunnel
should expose the Caddy HTTP origin without opening inbound web ports on the
router. Cloudflare terminates public HTTPS; Caddy binds HTTP on port 80 inside
the host and is reached only through the tunnel.

## Current launch blockers

- Cloudflare already has a `rendercart` tunnel for the root hostname, but it is
  currently down. Its locally managed route points to `http://localhost:8000`,
  so the host-side tunnel configuration must be updated to point at Caddy on
  `http://localhost:80`. Cloudflare marks its dashboard routes as locally
  managed, so make this change on the Ubuntu host. Keep the separate healthy
  `aspire7` tunnel used for SSH intact.
- The current zone has only the root app record and an SSH record. Add storage
  and analytics host routes to the existing tunnel only when those services
  are ready; do not create a duplicate tunnel.
- `main` still contains the legacy RenderCart app. The utility-tools tree is
  currently on `Feature-5` with uncommitted changes. Do not deploy `main` until
  the intended utility-tools tree has been reviewed and merged there.
- The Ubuntu machine has not been provisioned for RenderCart. Confirm it is
  intended to stay powered on, connected, and awake; a laptop that sleeps or
  loses home internet cannot provide durable public hosting.
- Pick the production domain/subdomains and configure the Cloudflare Tunnel.
- Create `/etc/rendercart/.env` with production-only secrets and mode `0600`.
  Never put that file in the repository or Actions logs. Start from
  `.env.example`, use unique random values, and set `APP_ENV=production`,
  `APP_BASE_URL`, `S3_PROXY_SITE`, `S3_PUBLIC_ENDPOINT`, `UMAMI_BASE_URL`,
  production auth/email/payment keys and the owner's `SUPER_ADMIN_EMAIL`.
- Configure the GitHub Actions runner as a service under a dedicated account
  that can run Docker. Register it with labels `self-hosted`, `linux`, `x64`,
  and `rendercart`; restrict repository access to trusted maintainers. Do not
  run deployment on pull requests or untrusted branches.
- Configure off-host encrypted backups for PostgreSQL and MinIO and verify a
  restore before calling the host durable. Docker volumes alone do not protect
  against disk failure or loss of the machine.

## Host preparation

1. Install Docker Engine and the Compose plugin from Docker's official Ubuntu
   repository; enable Docker at boot. Confirm the host has adequate free disk,
   memory, cooling and uninterrupted power for Postgres, Redis, MinIO, web, API,
   analytics and workers.
2. Create `/etc/rendercart/` owned by root, then create `.env` there with
   restricted permissions. Ensure the runner account can read it, but other
   local users cannot.
3. Install the GitHub Actions runner under a dedicated non-login service
   account, configure it as a systemd service, and apply the `rendercart`
   label. Do not run a second runner job concurrently with production deploys.
4. For this deployment, use `rendercart.app` as the public app hostname. Set
   `APP_BASE_URL=https://rendercart.app`, `CADDY_SITE_ADDRESS=:80`,
   `S3_PUBLIC_ENDPOINT=https://storage.rendercart.app`, and
   `S3_PROXY_SITE=http://storage.rendercart.app`. Set
   `UMAMI_BASE_URL=https://stats.rendercart.app` and
   `UMAMI_CADDY_SITE=http://stats.rendercart.app` when analytics is enabled.
   Configure Cloudflare Tunnel to route `rendercart.app`,
   `storage.rendercart.app`, and (if enabled) `stats.rendercart.app` to the
   host's Caddy HTTP listener on port 80. Keep API,
   Postgres, Redis, MinIO console, and admin interfaces private. Do not enable
   Cloudflare cache for API responses or signed file URLs.
5. Restrict direct access to the host and keep it patched. Avoid router port
   forwarding for HTTP/HTTPS; SSH should remain private (for example, through
   the existing private machine network).

## Deployment behavior

`.github/workflows/deploy.yml` runs after the `CI` workflow succeeds for a push
to `main`. It checks out that exact commit, checks for the host environment
file, validates Compose configuration, builds images on the host, applies
Alembic migrations, and starts the stack. Persistent named
volumes retain Postgres, Redis, MinIO, Caddy and Umami data across normal
redeploys. The workflow uses a concurrency lock so deploys do not overlap.

After the first deployment, check `docker compose -f infra/compose.yml ps`, the
GitHub Actions run, application health endpoints, login/email delivery, file
upload/download, Stripe test-mode webhooks, and Cloudflare origin behavior.
Keep Stripe in test mode until the live checkout and webhook configuration
have been verified.

## Recovery and backups

Before production use, implement scheduled encrypted off-host backups for the
RenderCart and Umami databases and MinIO buckets. Keep a documented restore
procedure and test it on a separate destination. A failed deployment can be
re-run after fixing the failing commit; to roll back, deploy a reviewed prior
commit through the same protected `main` workflow. Database migrations may
need a forward repair; do not assume an application image rollback reverses a
schema migration.
