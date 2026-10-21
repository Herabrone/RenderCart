# Stripe billing operations

## Catalog setup

Use Stripe test mode while developing. With the backend environment loaded and
`STRIPE_SECRET_KEY` set, run:

```powershell
uv run rendercart billing sync-products
```

The command creates or reuses Stripe products and prices using stable
`rendercart_key` metadata and prints the `STRIPE_PRICE_*` environment values.
Copy those values into the backend environment before enabling checkout. If a
price amount changes, Stripe requires a new Price; rerun the command and replace
the corresponding environment value. Existing historical prices remain in
Stripe and are not deleted.

## Webhooks in development

The local Compose development profile includes a Stripe CLI forwarder targeting
`/api/billing/webhook`. Authenticate Stripe CLI, run the configured profile,
and copy its generated signing secret into `STRIPE_WEBHOOK_SECRET`. The handler
verifies the raw payload signature and records the Stripe event ID in
`stripe_events` in the same database transaction as the fulfillment. A repeated
event ID returns success without running fulfillment twice.

Relevant events are Checkout completion and async-payment outcomes, subscription
created/updated/deleted, invoice paid/payment failed, charge refunded, and charge
dispute created. Pro access is derived from the subscription record and remains
active through Stripe's `past_due` retry window until the subscription period
ends or Stripe marks it canceled. Redirecting back from Checkout does not grant
access; the verified webhook does.

## Current implementation boundary

- Signed-in users can purchase Pro, a day pass, or a credit pack from
  `/account/billing`; the page also links to Stripe's customer portal.
- Guests can buy a day pass with an email address. After the paid webhook,
  RenderCart finds or creates a passwordless account, starts the pass, grants
  its credits, and emails a one-time sign-in link. Clicking that link verifies
  the email and claims the account.
- A signed-in user can choose a single-job S/M/L checkout from the paywall.
  The job stays in `awaiting_payment` until the verified webhook changes it to
  queued and inserts a `job_dispatches` outbox row. Celery Beat dispatches
  pending rows; the worker only claims a queued job, which makes duplicate
  dispatches safe. Unpaid jobs expire after one hour.
- `rendercart billing comp-pro EMAIL --days N --reason TEXT` adds a time-limited,
  audited Pro comp. `rendercart billing refund PURCHASE_UUID --reason TEXT`
  requests a Stripe refund; the verified refund webhook performs entitlement
  and credit revocation.
- Preview-then-pay is not implemented. Current reference tools run fully after
  the single-job payment; no preview output is locked for a later payment.
- Credit grants are tracked as FIFO lots; job holds reserve from the earliest
  expiring lots, failed jobs release those reservations, and the scheduled
  expiry task debits unspent credits while preserving currently held amounts.
  The migration seeds lots from grants and allocates historical negative ledger
  activity FIFO; the owner's production data should be reviewed before this
  migration is applied to any account with nonzero legacy credits.
- Unit coverage exists for guest pass fulfillment/claim, duplicate event
  idempotency, paid-job outbox release/dispatch, and Pro retry-window access.
  A real Stripe test-mode run and full checkout-to-worker E2E verification
  remain.

Keep Phase 2 marked partial until those flows and the acceptance criteria in
`PLAN.md` are complete and verified.
