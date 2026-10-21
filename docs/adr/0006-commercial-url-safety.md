# ADR 0006: Use commercial Web Risk lookups for dynamic QR targets

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

The business-generator plan requires URL threat checks before a dynamic QR target is saved and when a code is scanned. The original plan named Google Safe Browsing. Google's current guidance restricts Safe Browsing API use to non-commercial use and points revenue-generating services to Web Risk. RenderCart is a freemium revenue-generating service, so Safe Browsing v4 is not an appropriate production dependency.

## Decision

Use the Google Web Risk Lookup API (`uris.search`) for `MALWARE`, `SOCIAL_ENGINEERING`, `UNWANTED_SOFTWARE`, and `POTENTIALLY_HARMFUL_APPLICATION` checks. Cache by SHA-256 of the normalized URL in Redis, use the threat response expiration when present, and fail closed when the key is absent or the lookup is unavailable. Configure the API key as `GOOGLE_WEB_RISK_API_KEY`.

Dynamic QR redirects validate public HTTP(S) destinations with the existing DNS-resolving URL safety validator. The first scan increments analytics and returns an HTTP 302 to a RenderCart warning page that displays the destination host, a continue link, and an abuse-report link. The warning page checks the destination again before exposing the continue link. Scan analytics store time, device class, and country code without retaining the source IP; country is `ZZ` unless the trusted edge supplies a valid country header.

## Consequences

- The owner must enable Web Risk and provide a key before dynamic QR creation works.
- Web Risk charges above its current free monthly allowance; cache lookups and monitor usage in Google Cloud.
- Lookup URLs are sent to Google, so disclose this in the dynamic QR flow's privacy notice before launch.
- Dynamic QR URLs that become unsafe are disabled on scan and recorded in the audit log.
- Safe Browsing API v4 is not called from the public application.

## Sources

- [Google Safe Browsing appropriate usage](https://developers.google.com/safe-browsing/reference/Appropriate.Usage)
- [Google Web Risk Lookup API](https://docs.cloud.google.com/web-risk/docs/lookup-api)
- [Google Web Risk pricing](https://cloud.google.com/web-risk/pricing)
