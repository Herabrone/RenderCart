# 0007 — RenderCart workbench interface

## Context

The owner requested a complete UI redesign across the application, new assets, and removal of the purple visual style. The application has pivoted from Shopify image rendering to a general utility-tools platform. Its former pages repeated navigation and styling, exposed only three categories on the homepage, and gave account services little hierarchy.

## Decision

Use the warm neutral, ink, and burnt-orange workbench identity documented in `DESIGN.md`. Introduce one application shell, semantic theme tokens, a shared searchable directory for seven categories, a consistent tool workspace, and original SVG/social-preview assets. Refine authentication, account, billing, admin, legal, loading, empty, error, and job-result presentations within that system.

Preserve the existing Next.js/FastAPI stack, tool implementations, pricing/access policy, upload pipeline, billing authority, and restricted-route checks. This is an interface redesign, not a new product direction.

## Consequences

Both light and dark themes share semantic component roles. New screens can reuse the shell and category/workspace components. Browser verification must distinguish actual local tool execution from fixture-backed API presentation. Production payment, email, GPU/CPU processing, and staff operations still need their existing runtime acceptance checks.

## Verification findings

The existing nonce-based CSP was paired with statically prerendered interactive pages. The generated login HTML contained 19 script tags and zero nonce attributes. Root rendering now waits for the actual request via Next.js `connection()` so framework scripts can receive that request’s nonce. This preserves the strict policy and makes authentication/theme/form interactions compatible with it. Pages using the root layout consequently render dynamically, trading static page caching for the existing nonce strategy. See the [Next.js CSP guide](https://nextjs.org/docs/app/guides/content-security-policy).

The local Windows account cannot create standalone-package symlinks. `RENDERCART_LOCAL_PREVIEW=1` builds the same application without standalone packaging for local production-mode checks. CI and Docker continue to use standalone output by default.
