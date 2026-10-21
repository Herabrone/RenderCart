# RenderCart interface

RenderCart is an everyday utility workbench: documents, images, media, writing, business tasks, developer utilities, and calculators. Its interface should feel useful, calm, and approachable rather than like the former Shopify rendering product.

## Foundations

The source of truth is `apps/web/src/app/globals.css`. Use semantic tokens in components; both themes share the same roles.

| Role | Light | Dark | Purpose |
|---|---|---|---|
| Canvas | `#f8f7f3` | `#191c19` | Warm working surface |
| Surface | `#ffffff` | `#232722` | Forms, cards, results |
| Ink | `#252621` | `#efeee5` | Readable primary content |
| Muted | `#66685e` | `#b9bdb1` | Supporting information |
| Accent | `#b94324` | `#f38e65` | Primary action and active navigation |
| Line | `#e1e2d9` | `#3b4138` | Quiet grouping and separation |

Use sage, sky, butter, and terracotta surfaces to distinguish tool categories. They do not encode success, warning, or failure. Every status needs words or a recognizable icon as well as color.

Typography uses the system sans-serif stack for fast, self-contained UI. Georgia italic provides deliberate contrast in the two marketing statements; monospace labels are reserved for short category/utility labels. Headings use tight spacing, body copy uses generous line height, and numeric data uses tabular numerals where compared.

Controls have 44px minimum entry height and visible keyboard focus. Cards use 14–15px corners, controls about 9–10px, large panels about 18–20px. Fixed panels use borders and tonal contrast. Shadows are restrained and secondary.

## Shared composition

- `AppFrame` owns global navigation, responsive menu, theme preference, skip link, and legal footer. Keep account authorization in the existing API/server checks.
- `ToolCatalog` and `ToolCard` serve the directory and all seven categories, including calculators. Search survives category navigation and offers an explicit clear action.
- Tool pages present a breadcrumb, task title, workspace, and a compact usage/related-tools sidebar. Important quota/credit details stay available before submission.
- Authentication shares a quiet illustrated side panel on desktop and focuses on the form on mobile. Optional MFA and email-link paths remain accessible.
- Account services use expandable sections to avoid a long unstructured page. Admin data remains operational and uses anchors for navigation.
- File selection supports native keyboard-accessible picking, drag feedback, selected-file names/sizes, and removal. The same upload, validation, billing, and job pipeline remains authoritative.
- Job pages name their real state, expose progress accessibly, retain download/unlock controls, and provide a route back after failure/expiry.

## Assets and motion

`public/icon.svg` is the original RenderCart mark. `public/brand/workbench.svg` is the original file-transformation illustration. `src/app/opengraph-image.tsx` generates a matching social preview. These are code-native assets, with no stock artwork or external font dependency.

Motion is limited to brief interaction feedback and directional link affordances. Honor reduced motion. Do not manufacture processing time or imply a successful job before the API confirms it.

## Content and access

Use concise, task-specific labels. Distinguish no results from service unavailability. Preserve entered content on errors. Disclose paid limits and prices before commitment; do not invent popularity, urgency, or savings claims. Restricted screens and their server checks remain isolated; never add private tools to public navigation, metadata, search, or examples.
