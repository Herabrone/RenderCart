# Self-hosted analytics

RenderCart uses self-hosted Umami for privacy-conscious product analytics. The tracker is disabled until `UMAMI_WEBSITE_ID` is set. It runs at `UMAMI_BASE_URL` (a `stats.` subdomain in production), and browsers send analytics only to this owner-operated service.

## Local setup

1. Copy `.env.example` to `.env` and replace `UMAMI_APP_SECRET` and `UMAMI_DB_PASSWORD` with long, unique alphanumeric secrets. These values must remain stable so the Umami account and database continue to work.
2. Start the normal Compose stack. Compose starts `umami-db` and `umami` with the site; the database is stored in the `umami_data` volume.
3. Open `UMAMI_BASE_URL`, sign in to Umami, and change its initial `admin` / `umami` password immediately.
4. Add the RenderCart website in Umami, copy its website ID into `UMAMI_WEBSITE_ID`, and restart the `web` service.
5. Visit public pages and confirm pageviews/events appear in Umami. Confirm `/account`, `/admin`, `/jobs/*`, `/auth/*`, `/vault`, `/v/*`, `/p/*`, and `/f/*` do not create pageviews or custom events.

## Event and privacy rules

- `UMAMI_WEBSITE_ID` empty means no tracker script is rendered.
- Pageviews omit query strings and hashes. The tracker respects the browser's Do Not Track setting.
- Custom events may contain only public tool slugs and fixed product/event labels. Never include user text, file names, URLs submitted to a tool, account identifiers, emails, job IDs, payment session IDs, or tool options.
- `/account/billing?status=success` may send a generic `purchase-complete` event. Its query string and Stripe session ID are not sent.
- Do not add tracker scripts, data attributes, or analytics calls to Vault or expiring share routes.
- Update the privacy policy if the collected event set or provider changes. Configure separate Umami websites/IDs for production and non-production environments.

Umami's self-hosted Docker installation uses a PostgreSQL database and creates a default `admin` / `umami` login that must be changed on first use. See [Umami installation](https://docs.umami.is/docs/install) and [environment variables](https://docs.umami.is/docs/environment-variables).
