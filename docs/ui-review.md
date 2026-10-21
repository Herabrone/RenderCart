# Workbench UI review — 2026-10-21

## Implemented scope

- Shared brand, navigation, mobile menu, theme preference, skip link, and legal footer.
- Homepage with original workbench illustration, working search destinations, starting tools, and all seven categories.
- Unified directory/category navigation, including calculators, scoped search, result counts, clear search, no-results recovery, and a distinct service-degraded notice.
- Consistent workspace for the 39 current public processing manifests plus 44 browser tools. Existing specialized image/PDF/video/generator/chat panels use semantic theme tokens.
- Native/drag file selection with selected-file names, sizes, and removal, preserving the existing job submission pipeline.
- Sign-in, signup, email verification, magic link, and password reset; optional MFA and email-link paths are disclosed progressively. Recovery codes retain text entry. Request buttons have busy feedback.
- Account overview, navigable expandable services, security state, recent jobs, billing/credits, developer docs, admin sections, private workspace styling, and legal navigation.
- Loading, 404, application error, and job-state presentations. Job result/download/unlock controls remain connected to their existing API paths.
- Original icon/illustration/social preview, design contract, and ADR 0007.

## Checks completed

- TypeScript check and ESLint passed.
- 17 frontend unit tests passed, including three new catalog tests covering offline fallback, API failures, and duplicate slug handling.
- Optimized application build passed with `RENDERCART_LOCAL_PREVIEW=1`, including the existing Vault-isolation gate across 21 route manifests. Docker/CI keep standalone output by default; this Windows account cannot create standalone packaging symlinks.
- Read-only review of the deployed home and tool catalog established the baseline. Local screenshots inspected the new homepage, directory, category list, and word-counter workspace. Native GET search navigation, no-results feedback, clear-search recovery, and the calculator category were exercised.
- Contrast calculations: light accent/white 5.40:1; dark accent/button text 7.19:1; muted utility text/canvas 4.86:1; default control border/white 3.13:1; dark control border/surface 3.51:1.
- Existing strict CSP blocked the development runtime. Generated static sign-in HTML also had 19 scripts with no nonce. Root rendering now waits for each request so the existing nonce policy can apply; the policy was not relaxed. The rebuilt auth/account/pricing/tool routes are dynamic.

## Runtime verification still pending

Automatic approval review rejected starting the local production preview (including a loopback-bound attempt) with only “blocked by policy.” The owner explicitly approved the preview and GitHub push, but the preview start was again rejected by automatic review. Consequently the final production-mode visual/interaction pass is not yet complete; this limitation is disclosed with the pushed branch.

Remaining checks: theme persistence, mobile menu and narrow layouts, browser-tool input/output/copy/download, file add/remove and submission, optional auth paths/error recovery, account section navigation, admin/private layouts, and job ready/failure/expiry views. Any API-backed visual test should use local sample fixtures; no production payments, emails, jobs, or staff mutations were performed during this redesign.

CPU/GPU processing, real auth/email, Stripe fulfillment, and staff/Vault operations retain their broader product runtime acceptance requirements. Passing a fixture-backed UI check would not validate those integrations.
