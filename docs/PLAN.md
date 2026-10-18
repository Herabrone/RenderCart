# RenderCart — Master Plan & Agent Handoff

> **Read this whole document before writing any code.** It is the single source of truth for what RenderCart is, what has already been decided, and how to build it. If you are an AI agent picking this up, everything you need is here — you do not have access to the conversation that produced it.
>
> - **Owner / sole super admin:** Darian Lagman (git user `Darian Lagman`)
> - **Plan written:** 2026-10-17
> - **Status:** Planning complete. No application code exists yet. Next step is **Phase 0**.
> - **Keep this file current:** tick boxes in [§20 Status tracker](#20-status-tracker) as work lands, and record any decision that changes this plan in `docs/adr/` (see [§19](#19-how-to-work-in-this-repo-rules-for-agents)).

---

## Table of contents

1. [Background & history](#1-background--history)
2. [Product vision](#2-product-vision)
3. [Locked decisions (do not re-litigate)](#3-locked-decisions-do-not-re-litigate)
4. [Business model: pricing, credits, limits](#4-business-model-pricing-credits-limits)
5. [Access control (RBAC) & the restricted Vault](#5-access-control-rbac--the-restricted-vault)
6. [Tool catalog](#6-tool-catalog)
7. [System architecture](#7-system-architecture)
8. [Repository layout](#8-repository-layout)
9. [Tool registry & manifest spec](#9-tool-registry--manifest-spec)
10. [Job pipeline & file lifecycle](#10-job-pipeline--file-lifecycle)
11. [AI gateway & GPU workers](#11-ai-gateway--gpu-workers)
12. [Data model](#12-data-model)
13. [Authentication](#13-authentication)
14. [Billing (Stripe)](#14-billing-stripe)
15. [Frontend](#15-frontend)
16. [Security, abuse prevention & legal](#16-security-abuse-prevention--legal)
17. [Infrastructure, DevOps & observability](#17-infrastructure-devops--observability)
18. [Build phases with acceptance criteria](#18-build-phases-with-acceptance-criteria)
19. [How to work in this repo (rules for agents)](#19-how-to-work-in-this-repo-rules-for-agents)
20. [Status tracker](#20-status-tracker)
21. [Open questions for the owner](#21-open-questions-for-the-owner)
22. [Glossary](#22-glossary)

---

## 1. Background & history

- RenderCart **used to be** an AI product-image rendering service for Shopify stores: a FastAPI `image-service` with Alembic migrations, a React UI (`image-service/ui`), nginx reverse proxy, JWT + bcrypt auth, a `users` table and `shopify_stores` sync.
- On **2026-10-17** the owner took the project in a completely different direction. All previous code was deleted in commit **`527fa5e`** (`REMOVED: clear repository contents ahead of new project direction`) on branch `Feature-5`. The last commit containing the old code is **`4f1229f`**.
- **Do not restore the old app.** A few old files are worth *reading* as reference (view with `git show 4f1229f:<path>`):
  - `image-service/url_safety.py` + `tests/test_url_safety.py` — SSRF-safe URL validation. Good starting point for the safe fetcher in [§16](#16-security-abuse-prevention--legal).
  - `image-service/task_queue.py`, `image-service/model_loader.py` — earlier patterns for background jobs and lazy model loading.
  - `.github/workflows/ci.yml` — old CI workflow.
- Old tooling the owner was already using: Python 3.13, ruff (`.ruff.toml`), pytest, Docker, nginx, Alembic.

## 2. Product vision

RenderCart becomes an **all-in-one utility tools website** — "everything I could ever want" in one place (file converters, PDF tools, AI image tools, transcription, generators, developer tools, etc.).

It serves two purposes:

1. **Personal power tool for the owner.** As super admin, the owner gets access to *everything*, including legally risky tools that are never exposed to the public (the **Vault**, [§5.3](#53-the-vault-restricted-tools)).
2. **Income via freemium.** Public tools are free with limits; heavy use, batch processing, high-quality output, and AI features are monetized via a **$9.99/month Pro plan**, **day passes**, and **small one-time fees per job**.

Competitors/reference sites: TinyWow, iLovePDF (Premium from ~$9/mo), Smallpdf (from ~$15/mo), FreeConvert, CloudConvert, Convertio, remove.bg, Clockify's free tools.

Market evidence gathered during planning (Ahrefs "free tools SEO strategy" article; treat as directional, possibly dated):
- "file compressor" ~348K monthly searches, "mp3 converter" ~263K, "heic to jpg" ~207K.
- "calorie calculator" ~868K, "gpa calculator" ~550K, "paycheck calculator" ~378K.
- Free tools are an SEO traffic engine; long-tail tools have low keyword difficulty.
- People pay for: speed, no ads, no file-size caps, batch processing, and compute-heavy AI work (upscaling, transcription, background removal, OCR, chat-with-PDF).

Growth model: **free client-side tools + SEO landing pages bring traffic → generous-but-capped free tier on server tools → paywall at the moment of need (Pro / day pass / single job).**

## 3. Locked decisions (do not re-litigate)

These were decided with the owner. Change only with explicit owner approval and an ADR.

| Area | Decision |
|---|---|
| Frontend | **Next.js (App Router) + TypeScript**, Tailwind CSS, shadcn/ui, lucide icons |
| Backend API | **Python + FastAPI** (async), Pydantic v2, SQLAlchemy 2.x, Alembic |
| Background jobs | **Redis + Celery** workers, separate CPU and GPU queues |
| Database | **PostgreSQL** (+ `pgvector` extension for chat-with-PDF) |
| File storage | **S3-compatible object storage — MinIO** self-hosted (Cloudflare R2 is an acceptable swap later) |
| AI | **Owner's own GPU server(s)** run all models. **OpenRouter** is the fallback **for LLM tasks only** when own infra is busy/down |
| Hosting | **VPS + Docker Compose** (app server) + owner's GPU server(s) joined over a private network |
| Payments | **Stripe** (Checkout, Billing, Customer Portal, webhooks) |
| Sign-in | **Email + password, Google, GitHub, magic link** (all four) |
| Pricing | **Pro $9.99/month** for everything; **day passes**; **small one-time fees for single jobs** |
| RBAC | Roles `guest → free → day_pass → pro → admin → super_admin`. Owner is the **only** super admin |
| Risky tools | Live only in the **Vault**: super-admin-only, hidden, 404 to everyone else |
| Scope | **All six monetized categories** + free client-side tools + Vault are in scope (built in phases) |
| Name | Project stays **RenderCart** |

## 4. Business model: pricing, credits, limits

All numbers below are **initial defaults** and must live in config / the database (`tool_overrides`, `plans` settings), **never hard-coded in tool logic**, so the owner can tune them from the admin dashboard without deploys.

### 4.1 Plans & purchases

| Product | Price | What it grants |
|---|---|---|
| **Free (account)** | $0 | Free-tier limits on every public tool, job history for retention window |
| **Guest (no account)** | $0 | Lower limits than Free, Cloudflare Turnstile challenge on job submit |
| **Pro** | **$9.99 / month** (Stripe subscription) | All public tools, Pro limits, **1,000 credits/month** (reset each billing cycle, no rollover), priority GPU queue, no watermarks, batch, 24 h file retention, API access (Phase 8) |
| **Day Pass** | **$2.99** one-time | Pro entitlements for **24 hours** from purchase, **150 credits** (expire with pass) |
| **Single job** | **$0.99 (S) / $1.99 (M) / $2.99 (L)** one-time | Unlocks one job beyond free limits (tool declares its tier S/M/L) |
| **Credit packs** | 500 credits **$4.99** · 1,500 credits **$11.99** | Top-up for heavy users; purchased credits expire after 12 months |
| *Later:* Annual Pro | e.g. $79/year | Not at launch — see open questions |

**Fee warning to surface to the owner:** Stripe charges ~2.9% + $0.30 per card payment, so a $0.99 single job loses ~33% to fees. Mitigations to consider: steer single-job buyers to the $2.99 day pass in the paywall UI, or offer a small credit pack instead of $0.99 charges. Implement single-job pricing anyway (owner asked for it) but log conversion data so the owner can decide.

### 4.2 Credits

- **Credits only meter compute-heavy AI/GPU work.** Basic CPU tools (PDF merge, image convert, etc.) are unlimited for Pro under fair use (soft cap + rate limit).
- **Spend order:** expiring credits first (day-pass → monthly Pro → purchased packs).
- All movements go through an append-only **`credit_ledger`** (grant, spend, refund, expire). Balance = sum of ledger. Refund credits automatically if a job fails.
- Initial credit costs per tool are in the [§6](#6-tool-catalog) tables.

### 4.3 Free limits

- Counted **per subject per tool per UTC day**. Subject = `user_id` for logged-in users; for guests = hash of (guest cookie id + IP /24 for IPv4 or /64 for IPv6).
- Counters in Redis (`usage:{subject}:{tool_slug}:{yyyymmdd}`) for speed; every job also writes a `usage_events` row in Postgres for analytics.
- Check + increment atomically at job creation (Redis Lua script); decrement if the job fails for a system reason.
- Concurrency caps: guest 1 running job, free 2, day_pass/pro 5, admin/super_admin unlimited.

### 4.4 Paywall moments (UX contract)

When a user hits a limit, show **one modal** with three options, in this order: **Go Pro ($9.99/mo)** · **Day Pass ($2.99)** · **Just this job ($X)**. For "preview-then-pay" tools (watermarked / low-res result), show the free result *and* the paywall to unlock the full result.

## 5. Access control (RBAC) & the restricted Vault

### 5.1 Access levels

There is one ordered **access level** used everywhere:

```
guest < free < day_pass < pro < admin < super_admin
```

Implementation detail (important):
- **Stored staff role** on the user: `user` (default), `admin`, or `super_admin`.
- **Plan level** is *derived* from billing state at request time: `free`, `day_pass` (active pass not expired), or `pro` (active/trialing subscription). Not logged in = `guest`.
- **Effective level** = `max(plan_level, staff_role_level)`. Admin and super_admin automatically get Pro entitlements and are never charged or limited.
- Put this in one function, e.g. `rendercart.core.access.effective_level(user, now)`, cached per request. Every permission check uses it.

### 5.2 Role capabilities

| Level | Capabilities |
|---|---|
| guest | Public tools, guest limits, Turnstile on submit, can buy single jobs / day pass with email at checkout |
| free | Public tools, free limits, 2 h history |
| day_pass | Pro entitlements for 24 h |
| pro | Pro entitlements, credits, API keys (Phase 8) |
| admin | Pro entitlements + admin dashboard (users, jobs, abuse reports, tool flags). **No Vault.** Must have TOTP 2FA |
| super_admin | Everything, including the **Vault** and role management. Must have TOTP 2FA. **Exactly one: the owner** |

**Super admin bootstrap:** `SUPER_ADMIN_EMAIL` env var + CLI command `rendercart admin promote --email ... --role super_admin` run on the server. The super_admin role **cannot** be granted or removed through any web UI or API endpoint. Admin role can be granted only by super_admin via the dashboard. All role changes go to `audit_log`.

### 5.3 The Vault (restricted tools)

Tools that could create legal liability for the owner. **Super-admin only, invisible to everyone else.**

| Tool | Why restricted | Implementation |
|---|---|---|
| YouTube / TikTok / Instagram / X downloader (MP3/MP4) | Violates platform ToS, copyright risk | `yt-dlp` + ffmpeg |
| Watermark / object remover | Copyright circumvention risk | LaMa inpainting (GPU) + mask brush UI |
| PDF password unlocker | Could remove protection from others' docs | `pikepdf`/`qpdf` (owner-password removal; user-password requires known password) |
| URL shortener | Phishing/malware abuse magnet | Simple redirect table |
| Pastebin | Illegal content hosting risk | Text store with expiry |
| Temp file sharing (expiring links) | Illegal content hosting risk | MinIO presigned links |
| AI face swap / face generation | Deepfake risk | InsightFace-based pipeline (check model licenses — fine for private personal use only) |

**Enforcement requirements (all mandatory, all tested):**
1. Manifest field `restricted=True`. The **registry refuses to start** if any restricted tool has `min_level != super_admin` or `hidden != True`.
2. Vault API routes and pages return **404 (not 403)** for anyone below super_admin, so their existence is not revealed.
3. Restricted tools are excluded from: tool listings, search, sitemap, `robots`-indexable pages, the public OpenAPI schema, the public developer API, analytics events, and client JS bundles (load Vault UI via a separate route group fetched only after server-side check).
4. Every Vault action writes to `audit_log`.
5. Vault pages send `X-Robots-Tag: noindex, nofollow`.
6. Automated test suite asserts all of the above (see Phase 9).

**Default rule for new tools:** if a tool could plausibly expose the owner to copyright, ToS, abuse-hosting, or impersonation liability, mark it `restricted=True` and ask the owner before making it public.

Additional tools that are **public but must be gated against abuse**: Dynamic QR codes (they are URL redirects) — require a logged-in account, check targets against Google Safe Browsing / URLhaus, provide an abuse-report link on the interstitial, and allow admins to disable codes.

## 6. Tool catalog

Legend — **Runtime:** `client` (runs in browser, zero server cost), `cpu` (CPU worker), `gpu` (GPU worker), `llm` (AI gateway). **Job tier** = single-job price S $0.99 / M $1.99 / L $2.99. "Credits" applies to Pro/day-pass only; free users are limited by daily counts instead.

> ⚠️ **License check is mandatory before adopting any library or model.** Several popular choices are **AGPL** (forces open-sourcing a network service) or **non-commercial** model licenses. Notes below flag known risks but you must verify the current license at implementation time and record it in `docs/licenses.md`. **Default stance: avoid AGPL and non-commercial components in public tools** (they may be used in the Vault since that is private, personal use). See open question Q5.

### 6.1 Category A — PDF Suite (proven earner)

| Tool | Guest / Free | Pro | Credits | Job tier | Runtime | Implementation notes |
|---|---|---|---|---|---|---|
| Merge PDF | 2 / 3 per day, ≤10 MB, ≤5 files | Unlimited, ≤500 MB, ≤50 files | 0 | S | cpu | `pikepdf` (MPL-2.0) or `pypdf` (BSD) |
| Split / extract pages | 2 / 3 per day | Unlimited | 0 | S | cpu | `pikepdf` |
| Rotate / reorder / delete pages | 2 / 3 per day | Unlimited | 0 | S | cpu + client | Page thumbnails via `pypdfium2` (Apache/BSD); reorder UI with pdf.js |
| Compress PDF | 2 / 3 per day, ≤10 MB | Unlimited, ≤500 MB, quality presets | 0 | S | cpu | Image recompression via `pikepdf` + Pillow. ⚠️ Ghostscript is AGPL — avoid unless owner accepts (Q5) |
| PDF → Word | 1 / 2 per day | Unlimited | 1 per 10 pages | M | cpu | ⚠️ `pdf2docx` depends on PyMuPDF (AGPL). Evaluate alternatives or LibreOffice import; decide in Phase 3 ADR |
| PDF → Excel | 1 / 2 per day | Unlimited | 1 per 10 pages | M | cpu | `pdfplumber` (MIT) table extraction → `openpyxl` |
| PDF → JPG/PNG | 2 / 3 per day | Unlimited, high DPI | 0 | S | cpu | `pypdfium2` |
| Word/Excel/PPT/JPG → PDF | 2 / 3 per day | Unlimited | 0 | S | cpu (sandbox) | LibreOffice headless in sandboxed worker; images via `img2pdf` |
| OCR (scan → searchable PDF / text) | 1 page / 3 pages per day | Unlimited | 1 per 10 pages | M | cpu or gpu | `OCRmyPDF` (MPL-2.0) + Tesseract (Apache-2.0); GPU option docTR/PaddleOCR (Apache-2.0) |
| Edit PDF (text, images, annotations, fill forms) | Output watermarked | Clean output | 0 | S | client + cpu | Editing in browser with pdf.js (Apache-2.0) + `pdf-lib` (MIT); server flattens/finalizes |
| E-sign | 1 / month | Unlimited + audit trail (signer email, IP, timestamp, document hash) | 0 | M | client + cpu | Visual signature via pdf-lib; cryptographic signature via `pyHanko` (MIT) |
| Protect PDF (add password) | 2 / 3 per day | Unlimited | 0 | S | cpu | `pikepdf` encryption (adding protection is safe; *removing* it lives in Vault) |
| Batch mode (any PDF tool) | — | ✅ | per tool | — | cpu | Multi-file job with ZIP output |

### 6.2 Category B — AI Image Studio

| Tool | Guest / Free | Pro | Credits | Job tier | Runtime | Implementation notes |
|---|---|---|---|---|---|---|
| Background remover | Low-res preview (≤0.25 MP) | Full res, batch | 2 | S | gpu | `rembg` (MIT) with ISNet/BiRefNet (check weights license). ⚠️ BRIA RMBG is non-commercial — do not use publicly |
| AI upscaler 2× / 4× | 2× only, 1 / 3 per day, ≤2 MP input | 2× & 4×, batch, ≤16 MP | 2 (2×) / 5 (4×) | S/M | gpu | Real-ESRGAN (BSD-3); check model weight licenses |
| Photo enhancer / old-photo restore | 1 / 1 per day | Unlimited | 5 | M | gpu | GFPGAN (Apache-2.0) + Real-ESRGAN. ⚠️ CodeFormer is non-commercial (S-Lab) — Vault only |
| Image compressor | Free (traffic magnet), ≤20 files | Batch ≤200 + ZIP | 0 | — | client + cpu | Client-side via WASM (e.g. squoosh codecs) for small files; server `pyvips`/mozjpeg/oxipng for batch |
| Image converter (HEIC/WebP/PNG/JPG/AVIF/GIF) | Free (traffic magnet) | Batch + ZIP | 0 | — | client + cpu | `pillow-heif`, Pillow, `pyvips` |
| Product photo maker (white/colored bg + shadow) | Watermarked | Clean, batch, custom bg | 8 | M | gpu | Background removal → composite + generated soft shadow; optional AI background generation with a commercially licensed model (⚠️ FLUX.1-dev is non-commercial; FLUX.1-schnell is Apache-2.0 — verify) |
| Resize / crop / rotate / meme maker | Free | Free | 0 | — | client | Canvas-based |

### 6.3 Category C — Audio & Video Studio (user-uploaded files only — no platform downloading)

| Tool | Guest / Free | Pro | Credits | Job tier | Runtime | Implementation notes |
|---|---|---|---|---|---|---|
| Transcription (audio/video → text, timestamps, speakers) | 3 min / 10 min per month | Hours (credit-metered) | 1 per minute | M (≤60 min) / L (≤180 min) | gpu | `faster-whisper` (MIT) large-v3; diarization via pyannote (MIT, gated HF model — accept terms) |
| Subtitle / SRT / VTT generator | Branded burn-in only | Clean SRT/VTT/burn-in, styling | 1 per minute | M | gpu + cpu | Whisper → SRT; burn-in with ffmpeg |
| Subtitle translation | — | ✅ | +1 per minute | M | llm | AI gateway, segment-wise translation preserving timings |
| Vocal remover / stem splitter | 1 / 1 song per day, MP3 out | Unlimited, WAV, 4-stem | 5 per song | S | gpu | Demucs (MIT) |
| Video compressor | ≤100 MB | ≤2 GB, priority | 1 per 100 MB | S/M | cpu or gpu | ffmpeg (use LGPL build or invoke as separate binary; NVENC on GPU host) |
| Video converter / trimmer / merger / to-GIF | ≤100 MB | ≤2 GB | 0 (fair use) | S | cpu | ffmpeg; trim UI in browser |
| Audio converter / trimmer / ringtone maker | Free ≤50 MB | ≤1 GB, batch | 0 | — | cpu (or client via ffmpeg.wasm) | ffmpeg |
| Audio extractor (video → MP3/WAV) | ≤100 MB | ≤2 GB | 0 | S | cpu | ffmpeg |
| Text to speech | 500 chars, basic voice | 100K chars/job, premium voices, MP3/WAV | 1 per 1K chars | S/M | gpu | Kokoro (Apache-2.0) recommended. ⚠️ XTTS-v2 (Coqui CPML) is non-commercial; check Piper's current license |
| Noise removal / audio enhance | 1 / 1 per day | Unlimited | 2 per 10 min | S | gpu | e.g. DeepFilterNet (MIT/Apache) |

### 6.4 Category D — AI Writing & Summaries

| Tool | Guest / Free | Pro | Credits | Job tier | Runtime | Implementation notes |
|---|---|---|---|---|---|---|
| Summarizer (text / PDF / URL / transcript) | 1 / 3 per day, ≤5K words | Unlimited length (chunked map-reduce) | 2 per doc (+1 per 10K words) | S | llm | URL fetch via safe fetcher + `trafilatura` (Apache-2.0) |
| Chat with PDF / document | 1 doc, 10 questions / day | Unlimited docs, history | 5 per doc indexed + 1 per question | M | llm + gpu | Chunk → embed (`bge-m3`, MIT, on GPU) → `pgvector` → LLM answer with page citations |
| Paraphraser / rewriter (tones) | 500 words / day | 10K words per run | 1 per 1K words | S | llm | — |
| Grammar & spelling fixer | 500 words / day | 10K words per run | 1 per 1K words | S | llm | Optionally LanguageTool server (LGPL) for deterministic checks |
| Document translator (keeps formatting) | 1 page | Full docs (DOCX/PDF/PPTX/TXT) | 2 per page | M/L | llm + cpu | DOCX: translate runs via `python-docx`; PDF: convert → translate → rebuild |
| AI writing helpers (email writer, title/caption generator, etc.) | 3 / day | Unlimited (fair use) | 1 per run | — | llm | Prompt templates; add incrementally |

### 6.5 Category E — Business Generators

| Tool | Guest / Free | Pro | Credits | Job tier | Runtime | Implementation notes |
|---|---|---|---|---|---|---|
| Invoice / receipt / quote generator | Branded "Made with RenderCart" footer | Own logo, saved clients/items, recurring invoices, numbering, multi-currency | 0 | S | cpu | HTML templates → PDF via WeasyPrint (BSD) or headless Chromium; data saved in Postgres |
| Resume / CV builder + cover letter | 1 template, branded | All templates, AI rewrite, multiple resumes | 2 per AI rewrite | M | cpu + llm | Structured JSON resume → templates → PDF/DOCX |
| QR code generator (static) | Free (traffic magnet) | Free | 0 | — | client | `qrcode`/`segno` equivalent in JS; logos, colors, SVG/PNG |
| **Dynamic QR codes** (editable target + scan analytics) | — (account required, 1 code) | Unlimited codes, analytics (time, country, device), logo, custom domain later | 0 | — | cpu | Redirect endpoint `/q/{code}` logs scan → 302. Geo via MaxMind GeoLite2 (license/attribution). **Abuse gating required** ([§5.3](#53-the-vault-restricted-tools)) |
| Barcode generator | Free | Free | 0 | — | client | JsBarcode / bwip-js |
| Email signature generator | Basic templates | Premium templates, no branding | 0 | — | client | HTML output + copy-to-clipboard |
| Business card generator | Branded | Print-ready PDF (bleed, CMYK note) | 0 | S | cpu | HTML → PDF |

### 6.6 Category F — Developer & Website Tools

| Tool | Guest / Free | Pro | Credits | Job tier | Runtime | Implementation notes |
|---|---|---|---|---|---|---|
| Uptime monitor | 1 site, 15-min checks, email alerts (account required) | 20 sites, 1-min checks, email + Discord/Slack webhook + SMS (capped) | 0 (SMS: 1 credit each) | — | cpu (scheduler) | Celery beat schedules checks; results in `monitor_checks`; status page per user later. SMS via Twilio (see Q10) |
| SSL certificate & domain expiry alerts | 1 domain | Unlimited | 0 | — | cpu | TLS handshake cert inspection; domain expiry via RDAP |
| Website speed / SEO audit | 1 report / day | Scheduled weekly reports, history, PDF export | 2 per report | S | cpu (sandbox) | Lighthouse CLI (Apache-2.0) in sandboxed headless Chromium; SSRF-safe target validation |
| Public developer API (all public tools) | — | Included for Pro; per-call credit billing | per tool | — | api | API keys, rate limits, OpenAPI docs at `/developers` (Phase 8) |
| Webhook tester / request bin | 1 bin, 1 h | 10 bins, 7 days | 0 | — | cpu | ⚠️ Consider abuse; requires account |

### 6.7 Free client-side tools (traffic magnets, zero server cost)

Run 100% in the browser; each gets its own SEO landing page. Build these early — they drive traffic to the paid tools. Optionally show a tasteful cross-sell ("Need to compress 200 images? Go Pro").

- **Text:** word & character counter, case converter, text diff/compare, lorem ipsum, slug generator, remove duplicates/sort lines, Markdown ↔ HTML.
- **Developer:** JSON formatter/validator, JSON ↔ YAML ↔ CSV, Base64 encode/decode, URL encode/decode, JWT decoder, regex tester, cron expression builder, hash generator (MD5/SHA-1/SHA-256), UUID generator, password generator, timestamp converter, color converter (HEX/RGB/HSL).
- **Calculators:** percentage, tip, loan, mortgage, age, date difference/countdown, GPA, calorie (BMR/TDEE), unit converter, military-time converter, time-zone converter, currency converter (rates fetched server-side daily from a free source such as the ECB feed and cached).
- **Image (canvas/WASM):** crop, resize, rotate, color picker & palette extractor, favicon generator, EXIF viewer/remover, meme maker.
- **Generators:** static QR, barcode, email signature.

### 6.8 Tool count summary

~13 PDF · ~7 Image · ~10 Audio/Video · ~6 Writing · ~7 Business · ~5 Dev/Web · ~40 client-side · 7 Vault.

## 7. System architecture

```
                             Internet
                                │
                       ┌────────▼────────┐
                       │      Caddy      │  TLS (auto HTTPS), HTTP/2/3, rate limits,
                       │ reverse proxy   │  security headers, large-upload passthrough
                       └───┬─────────┬───┘
               /*          │         │   /api/*  (same origin → cookies just work)
                 ┌─────────▼──┐   ┌──▼──────────────┐
                 │  web       │   │  api            │  FastAPI (uvicorn workers)
                 │  Next.js   │──▶│  auth, RBAC,    │  billing, tool registry,
                 │  SSR/SSG   │   │  jobs, webhooks │  presigned uploads, SSE progress
                 └────────────┘   └──┬──────┬───┬───┘
                                     │      │   │
                     ┌───────────────▼┐ ┌───▼───▼──────┐ ┌─────────────────────┐
                     │ PostgreSQL     │ │ Redis        │ │ MinIO (S3)          │
                     │ + pgvector     │ │ broker, cache│ │ uploads / results / │
                     └────────────────┘ │ counters,    │ │ persistent buckets  │
                                        │ pub/sub      │ └─────────▲───────────┘
                                        └──▲───────▲───┘           │
                     ┌─────────────────────┘       │               │
         ┌───────────┴────────────┐   ┌────────────┴──────────────┐│
         │ CPU workers (VPS)      │   │ GPU workers (GPU server/s)││
         │ queues: cpu.default,   │   │ queues: gpu.image,        ││
         │ cpu.heavy, cpu.sandbox │   │ gpu.audio, gpu.embed      ││
         │ + celery beat scheduler│   │ (+ .priority variants)    ││
         └────────────────────────┘   └───────────────────────────┘│
                                        ┌──────────────────────────┐│
         AI gateway (library inside     │ vLLM (OpenAI-compatible) ││
         api + workers) ───────────────▶│ on GPU server: chat LLM  ││
              │ fallback (LLM only)     │ + embeddings             ││
              ▼                         └──────────────────────────┘│
          OpenRouter API                                            │
                                                                    │
   VPS ⟷ GPU server(s) linked by Tailscale/WireGuard private network ┘
   Redis, Postgres, MinIO listen ONLY on private interfaces.

   External services: Stripe, transactional email (Resend default), Cloudflare
   Turnstile, Google/GitHub OAuth, Sentry, Google Safe Browsing, MaxMind GeoLite2.
```

Key principles:
- **API is the security boundary.** All authorization and limit checks happen in FastAPI. Next.js middleware may redirect for UX but is never trusted.
- **Same origin.** `https://<domain>/` → Next.js, `https://<domain>/api/` → FastAPI. Auth cookies are first-party; no CORS needed for the site.
- **Every server-side tool runs as a job**, even fast ones, giving one uniform code path for limits, credits, billing, progress, retention, and retries.
- **Workers are stateless.** They pull inputs from MinIO, write outputs to MinIO, report progress via Redis pub/sub, and update the `jobs` row.
- **Horizontal scale:** add CPU worker containers on more VPSs and GPU workers on more GPU boxes; they all join the same Redis queues.

## 8. Repository layout

Monorepo. Python managed with **uv** (workspace), JS with **pnpm** workspaces.

```
RenderCart/
├── docs/
│   ├── PLAN.md                  ← this file
│   ├── adr/                     ← Architecture Decision Records (0001-*.md, …)
│   ├── licenses.md              ← every third-party lib/model + license + where used
│   └── runbooks/                ← deploy, backup/restore, rotate secrets, add a GPU node
├── apps/
│   └── web/                     ← Next.js app (App Router, TS)
│       ├── app/
│       │   ├── (marketing)/     ← home, pricing, category pages, legal
│       │   ├── (tools)/tools/[slug]/   ← generic + custom tool pages
│       │   ├── (account)/account/…     ← profile, billing, history, api keys
│       │   ├── (admin)/admin/…         ← admin dashboard (server-checked)
│       │   └── (vault)/vault/…         ← super-admin only; separate bundle
│       ├── components/          ← ui (shadcn), tool-runner, uploader, paywall, …
│       ├── client-tools/        ← implementations of §6.7 browser-only tools
│       └── lib/api/             ← generated TS client from FastAPI OpenAPI
├── backend/
│   ├── pyproject.toml           ← uv workspace root
│   ├── src/rendercart/
│   │   ├── core/                ← config (pydantic-settings), db, redis, storage, access/RBAC, logging, security
│   │   ├── auth/                ← passwords, sessions, OAuth, magic links, TOTP, API keys
│   │   ├── billing/             ← Stripe checkout, webhooks, entitlements, credits ledger
│   │   ├── jobs/                ← celery app, base task, job service, progress, retention
│   │   ├── ai/                  ← AI gateway, providers (vllm, openrouter, local-gpu), cost tracking
│   │   ├── safety/              ← safe URL fetcher (SSRF), file validation, Turnstile, Safe Browsing
│   │   ├── registry/            ← ToolManifest models, discovery, validation
│   │   ├── tools/
│   │   │   ├── pdf/merge/       ← manifest.py, options.py, run.py, tests/
│   │   │   ├── pdf/compress/ …
│   │   │   ├── image/… audio/… video/… writing/… business/… dev/…
│   │   │   └── vault/…          ← restricted tools (super_admin only)
│   │   ├── api/                 ← FastAPI app + routers (auth, tools, jobs, billing, admin, vault, public API, qr redirect)
│   │   ├── admin/               ← admin services
│   │   └── cli.py               ← `rendercart` CLI (promote admin, seed, cleanup, etc.)
│   ├── migrations/              ← Alembic
│   └── tests/                   ← cross-cutting tests (rbac, billing, registry invariants)
├── infra/
│   ├── compose.yml              ← base services
│   ├── compose.dev.yml          ← hot reload, Mailpit, stripe-cli, exposed ports
│   ├── compose.prod.yml         ← prod overrides, resource limits
│   ├── gpu/compose.gpu.yml      ← GPU worker + vLLM for the GPU server
│   ├── caddy/Caddyfile
│   ├── docker/                  ← Dockerfiles: api, worker-cpu, worker-sandbox, worker-gpu, web
│   └── monitoring/              ← prometheus, grafana dashboards, alert rules
├── .github/workflows/           ← CI (see §17)
├── justfile                     ← cross-platform task runner (owner is on Windows 11)
├── .env.example
└── README.md
```

## 9. Tool registry & manifest spec

Every server-side tool is a **self-contained module** under `backend/src/rendercart/tools/<category>/<tool>/`. Adding a tool = adding a folder. The registry auto-discovers manifests at startup and validates them.

### 9.1 Manifest (Pydantic model, sketch)

```python
# backend/src/rendercart/tools/pdf/merge/manifest.py
from rendercart.registry import (
    ToolManifest, Category, Level, Runtime, Queue, JobTier, Limit, FileInput, SeoMeta,
)
from .options import MergeOptions

TOOL = ToolManifest(
    slug="merge-pdf",                     # URL: /tools/merge-pdf ; unique, kebab-case, stable forever
    name="Merge PDF",
    category=Category.PDF,
    summary="Combine multiple PDFs into one file.",
    min_level=Level.GUEST,                # minimum access level to see/use the tool
    restricted=False,                     # True → Vault; registry enforces super_admin + hidden
    hidden=False,                         # excluded from listings/sitemap/search
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    ui="generic",                         # "generic" (auto form) | "custom" (bespoke React page)
    inputs=FileInput(
        accept=["application/pdf"],
        min_files=2,
        max_files={Level.GUEST: 5, Level.FREE: 5, Level.PRO: 50},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    options=MergeOptions,                 # Pydantic model → JSON Schema → auto-generated form
    limits={
        Level.GUEST: Limit.per_day(2),
        Level.FREE: Limit.per_day(3),
        Level.PRO: Limit.unlimited(fair_use_per_hour=120),
    },
    credit_cost=0,                        # int, or callable(job_inputs) -> int for metered tools
    job_tier=JobTier.S,                   # single-job unlock price
    preview_then_pay=False,               # True → free tier gets preview; full result unlocked by payment
    timeout_s=300,
    seo=SeoMeta(
        title="Merge PDF Online — Free & Fast | RenderCart",
        description="Combine PDF files in seconds…",
        faq=[("Is it free?", "Yes, up to 3 merges per day…")],
        keywords=["merge pdf", "combine pdf"],
    ),
)
```

```python
# backend/src/rendercart/tools/pdf/merge/run.py
from rendercart.jobs import JobContext

def run(ctx: JobContext, options: MergeOptions) -> None:
    paths = ctx.download_inputs()          # MinIO → temp dir
    ctx.progress(10, "Merging…")
    out = ctx.output_path("merged.pdf")
    ...                                    # do the work
    ctx.upload_output(out, content_type="application/pdf")
    ctx.progress(100, "Done")
```

### 9.2 Registry invariants (enforced at startup and in tests)

- Slugs unique and kebab-case; `restricted=True ⇒ min_level == SUPER_ADMIN and hidden == True`.
- `runtime == GPU ⇒ queue in GPU queues`; `credit_cost` defined for every GPU/LLM tool.
- Every non-client tool has a `run` callable and at least one test with a fixture input.
- Effective limits = manifest defaults **overridden by** `tool_overrides` rows (admin-editable), so pricing/limits change without deploys. Admins can also **disable** a tool instantly.

### 9.3 Registry API

- `GET /api/tools` → public manifests for the caller's level (never restricted ones unless super_admin).
- `GET /api/tools/{slug}` → manifest + options JSON Schema + caller's remaining quota/credits. Restricted slug + non-super-admin → **404**.
- Client-side tools are declared in a parallel TS registry in `apps/web/client-tools/registry.ts` (same `slug/name/category/seo` fields) so listing, search, and sitemap include them.

## 10. Job pipeline & file lifecycle

### 10.1 States

```
created ──▶ awaiting_payment ──▶ queued ──▶ running ──▶ succeeded
   │               │                │          │──────▶ failed (credits refunded, quota restored if system error)
   │               └──▶ abandoned   └──▶ cancelled
   └──────────────▶ queued (if within limits / entitled)
succeeded ──▶ expired (files deleted after retention)
```

### 10.2 Flow

1. **Upload.** Client calls `POST /api/uploads` (tool slug, file names, sizes, mime) → API checks size/type limits for caller level → returns **presigned PUT URLs** (multipart for >50 MB) to MinIO `uploads` bucket under `uploads/{subject}/{upload_id}/…`. Browser uploads directly to MinIO (via Caddy route `/s3/` or a storage subdomain) with progress.
2. **Create job.** `POST /api/tools/{slug}/jobs` with `upload_ids` + `options`. API: validates options against the manifest model → verifies Turnstile (guests) → checks access level → checks & increments quota atomically → reserves credits (ledger `hold`) → creates `jobs` row → enqueues Celery task to manifest queue (priority variant for paid levels). If over limit and not entitled → returns `402 Payment Required` with paywall options.
3. **Run.** Worker downloads inputs, **validates real file type by magic bytes** (never trust extension/mime), runs the tool with timeout + resource limits, uploads outputs to `results/…`, publishes progress to Redis channel `job:{id}`.
4. **Progress to browser.** `GET /api/jobs/{id}/events` is a **Server-Sent Events** stream fed by Redis pub/sub (fallback: polling `GET /api/jobs/{id}`).
5. **Result.** `GET /api/jobs/{id}/download` checks ownership and payment state → 302 to a **short-lived presigned GET URL** (5 min).
6. **Finalize credits.** On success convert `hold` → `spend`; on failure release hold.
7. **Retention.** Inputs + outputs deleted after retention: **guest 1 h · free 2 h · day_pass/pro 24 h** (configurable). Enforced twice: a Celery beat cleanup task (deletes objects + marks job `expired`) and MinIO lifecycle rules on `uploads/` and `results/` (1-day safety net).
8. **Ownership.** Guests own jobs via a signed `rc_guest` cookie id; if they sign up within the session, their guest jobs are attached to the new account.

### 10.3 Buckets

| Bucket | Contents | Retention | Backed up |
|---|---|---|---|
| `uploads` | Raw user inputs | ≤24 h | No |
| `results` | Tool outputs | ≤24 h | No |
| `persistent` | Logos, signatures, saved invoice/resume assets, dynamic QR logos | Until user deletes / account deletion | **Yes** |
| `vault` | Vault outputs & temp shares | Configurable by super admin | No |

### 10.4 Queues

| Queue | Host | Concurrency guidance | Used by |
|---|---|---|---|
| `cpu.default` | VPS | = CPU cores | Fast PDF/image ops, generators |
| `cpu.heavy` | VPS | low (2–4) | ffmpeg, large PDFs, OCR (CPU), Lighthouse |
| `cpu.sandbox` | VPS (hardened container) | low | LibreOffice, any untrusted-format converter |
| `gpu.image`, `gpu.image.priority` | GPU | per GPU VRAM | bg removal, upscale, enhance, product photo, inpainting |
| `gpu.audio`, `gpu.audio.priority` | GPU | per GPU VRAM | Whisper, Demucs, TTS, denoise |
| `gpu.embed` | GPU | high | embeddings for chat-with-PDF |
| `scheduler` | VPS | 1 (celery beat) | uptime checks, SSL checks, cleanup, credit resets, currency rates |

Workers consume `*.priority` before normal queues. When normal GPU queue depth exceeds a threshold (admin-configurable), free/guest submissions get "High demand — try again shortly, or skip the line with Pro/Day Pass".

## 11. AI gateway & GPU workers

### 11.1 Owner's infrastructure

The owner has **their own GPU server(s)**. Exact GPU models/VRAM/count and network location are **unknown — ask (Q1)**. Plan assumes: Linux, Docker + NVIDIA Container Toolkit available, reachable from the VPS over Tailscale/WireGuard.

On each GPU server run (`infra/gpu/compose.gpu.yml`):
- **Celery GPU workers** for non-LLM models (image, audio, embeddings), loading models lazily and keeping hot models resident in VRAM with an LRU policy; one worker process per GPU (`CUDA_VISIBLE_DEVICES`).
- **vLLM** serving an open-weight chat model (choose a commercially licensed one, e.g. a Qwen or Llama family model sized to VRAM — verify license) and an embeddings model, via its **OpenAI-compatible HTTP API**.
- Exporters: node-exporter + NVIDIA DCGM exporter for Prometheus.

### 11.2 Gateway (`backend/src/rendercart/ai/`)

A thin internal library used by API and workers. Single entry points by **capability**, not by vendor:

```python
ai.chat(messages, task="summarize", max_tokens=..., json_schema=None, priority=...)
ai.embed(texts, task="pdf-chat")
```

- **Routing for LLM tasks:** primary = own vLLM; on timeout, 5xx, connection error, or when own-infra queue/latency exceeds a threshold → **OpenRouter** (OpenAI-compatible API, so both use the same client). Per-task model mapping lives in config (`ai_models.yaml` or DB), e.g. `summarize: {primary: "vllm/<model>", fallback: "openrouter/<model>"}`.
- **Health:** background health checks mark providers up/down; circuit breaker opens after N consecutive failures.
- **Privacy:** when falling back to OpenRouter, request providers with zero-data-retention / no-training policies where available. Disclose third-party AI processing in the privacy policy.
- **Non-LLM GPU tasks have no external fallback** (OpenRouter can't remove backgrounds, upscale, or transcribe). Overload is handled by queueing + priority + "high demand" messaging. Future option: a Replicate/fal.ai fallback provider behind the same interface — **not in scope** unless the owner asks.
- **Accounting:** every call writes `ai_usage` (provider, model, task, tokens in/out, gpu_seconds, est_cost_usd, job_id, fallback_used). Admin dashboard shows fallback rate and OpenRouter spend; add a **monthly OpenRouter spend cap** (config) after which fallback is disabled and LLM jobs queue instead.
- **Dev mode:** `AI_MODE=remote|local-cpu|mock`. `mock` returns canned outputs so the whole app runs on a laptop without GPUs; `local-cpu` runs tiny models for integration tests.

## 12. Data model

PostgreSQL via SQLAlchemy 2.x + Alembic. UUIDv7 (or ULID) primary keys, `created_at`/`updated_at` timestamps everywhere, money stored as integer cents.

| Table | Key columns / purpose |
|---|---|
| `users` | id, email (unique, citext), email_verified_at, password_hash (nullable), display_name, staff_role (`user`/`admin`/`super_admin`), totp_secret_enc, is_banned, stripe_customer_id, deleted_at |
| `oauth_accounts` | user_id, provider (`google`/`github`), provider_user_id, email |
| `sessions` | id (hashed token), user_id, created_at, last_seen_at, expires_at, ip, user_agent, mfa_verified |
| `auth_tokens` | hashed token, user_id/email, purpose (`magic_link`/`verify_email`/`reset_password`), expires_at, used_at |
| `api_keys` | user_id, name, prefix, key_hash, last_used_at, revoked_at |
| `subscriptions` | user_id, stripe_subscription_id, status, current_period_start/end, cancel_at_period_end |
| `day_passes` | user_id (or guest email), starts_at, ends_at, stripe_payment_intent_id |
| `purchases` | user_id/guest_id, kind (`single_job`/`credit_pack`/`day_pass`), amount_cents, stripe_checkout_session_id, job_id (nullable), status |
| `stripe_events` | stripe event id (unique) — webhook idempotency |
| `credit_ledger` | user_id, delta, kind (`grant_monthly`/`grant_daypass`/`purchase`/`hold`/`spend`/`release`/`refund`/`expire`/`admin_adjust`), expires_at, job_id, note |
| `jobs` | id, tool_slug, owner user_id / guest_id, level_at_creation, status, options jsonb, input_keys, output_keys, progress, error_code/error_message, credits_reserved/spent, paid_purchase_id, priority, started_at, finished_at, expires_at |
| `usage_events` | subject, tool_slug, job_id, level, created_at — analytics/limits audit |
| `tool_overrides` | tool_slug, enabled, limits jsonb, credit_cost, job_tier, updated_by |
| `ai_usage` | job_id, provider, model, task, tokens_in/out, gpu_seconds, est_cost_usd, fallback_used |
| `documents`, `document_chunks` | chat-with-PDF: chunk text, page, `embedding vector(n)` (pgvector, HNSW index) |
| `qr_codes`, `qr_scans` | dynamic QR: code, target_url, owner, disabled; scans: ts, country, device, referrer (no raw IP stored — hash/truncate) |
| `monitors`, `monitor_checks`, `alert_channels` | uptime/SSL/domain monitors, check results, alert targets |
| `invoices`, `invoice_clients`, `invoice_items` | business generator saved data |
| `resumes` | user_id, data jsonb, template |
| `abuse_reports` | target type/id, reporter, reason, status |
| `audit_log` | actor_user_id, action, target, metadata jsonb, ip, ts — all admin/vault/role/billing-override actions |
| `vault_*` | short links, pastes, file shares (super admin only) |

## 13. Authentication

FastAPI **owns auth** (single source of truth for the website *and* the public API). The old repo used JWT + bcrypt — **do not reuse**; use server-side sessions as below.

- **Sessions:** opaque random token in cookie `rc_session` (`HttpOnly; Secure; SameSite=Lax; Path=/`), stored hashed in `sessions` (+ Redis cache). Revocable, rotated on login and privilege change. Sliding expiry 30 days; admin sessions 12 h.
- **CSRF:** SameSite=Lax plus a required custom header (`X-RC-CSRF` double-submit token) on all state-changing `/api` requests from the browser.
- **Email + password:** argon2id (`argon2-cffi`), min length 10, check against breached passwords via HIBP k-anonymity API (optional, fail-open). Email verification required before purchases and dynamic-QR/monitor creation.
- **Google & GitHub OAuth:** Authlib, authorization-code flow with PKCE + state. Link to an existing account only when the provider email is verified and matches.
- **Magic link:** single-use token, 15-minute expiry, stored hashed; rate-limited per email and IP.
- **Password reset:** same token mechanism, invalidates all sessions on success.
- **2FA:** TOTP (`pyotp`) + recovery codes. **Mandatory for admin and super_admin**; optional for everyone else.
- **API keys (Phase 8):** `rc_live_<random>`; show once; store prefix + hash; `Authorization: Bearer`.
- **Rate limits:** login/magic-link/reset endpoints limited per IP and per email (Redis).
- **Transactional email:** provider TBD (Q3) — default **Resend**; **Mailpit** in dev. Templates: verify email, magic link, reset password, welcome, subscription canceled/payment failed (Stripe also emails), credits low, uptime/SSL alerts, day pass expiring.
- **Account deletion & export** (GDPR-style): self-serve, deletes personal data and persistent files, anonymizes ledger/purchases needed for accounting.

## 14. Billing (Stripe)

### 14.1 Stripe objects (create via a seed script `rendercart billing sync-products`, store IDs in config)

- Product **RenderCart Pro** → recurring price **$9.99/month** (USD).
- Product **Day Pass** → one-time **$2.99**.
- Product **Single Job** → one-time prices **S $0.99, M $1.99, L $2.99**.
- Product **Credit Pack** → one-time **500 credits $4.99**, **1,500 credits $11.99**.

### 14.2 Flows

- **Upgrade to Pro:** `POST /api/billing/checkout {product:"pro"}` → Stripe Checkout (subscription mode, customer = user's stripe_customer_id, created on demand) → redirect back to `/account/billing?status=success`. **Entitlement is granted only by webhook**, never by the redirect.
- **Manage/cancel:** Stripe Customer Portal session.
- **Day pass / credit pack:** Checkout in payment mode. Guests may buy a day pass with email; on webhook, find-or-create a user by that email (unverified) and email a magic link to claim it.
- **Single job (pre-pay):** job is created in `awaiting_payment` with inputs already uploaded → Checkout with `metadata.job_id` → webhook marks purchase paid and enqueues job (with Pro-level limits for that job only) → user returns to `/jobs/{id}` showing progress. Abandoned after 1 h → inputs deleted.
- **Single job (preview-then-pay):** job runs at free tier producing preview **and** stores the full result locked; payment unlocks download.

### 14.3 Webhooks (`POST /api/billing/webhook`)

Verify signature; store `event.id` in `stripe_events` (skip duplicates); process in a transaction.

| Event | Action |
|---|---|
| `checkout.session.completed` | Fulfil day pass / credit pack / single job (by metadata) ; link subscription |
| `customer.subscription.created` / `updated` | Upsert `subscriptions`; status drives `pro` level |
| `customer.subscription.deleted` | Downgrade to free at period end |
| `invoice.paid` | Grant monthly 1,000 credits (expire at period end) |
| `invoice.payment_failed` | Flag account; Stripe Smart Retries/dunning handle emails; keep Pro during retry window |
| `charge.refunded` / `charge.dispute.created` | Revoke entitlement/credits as appropriate, log to `audit_log`, notify owner |

### 14.4 Other

- **Taxes:** Stripe Tax on/off is an owner decision (Q4). Code should support enabling `automatic_tax` via config.
- **Refund policy:** credits auto-refund on failed jobs; money refunds manual via admin dashboard (calls Stripe Refunds API, logged).
- **Testing:** Stripe test mode + `stripe listen --forward-to` (stripe-cli container in `compose.dev.yml`); webhook handler tests using recorded fixture events.
- **Admin overrides:** super_admin/admin can grant credits or comp Pro (logged); stored as `admin_adjust` ledger entries or comp flag.

## 15. Frontend

- **Stack:** Next.js App Router, TypeScript strict, Tailwind, shadcn/ui, lucide-react, TanStack Query for client data, react-hook-form + zod (or a JSON-Schema form renderer) for tool options, next-intl ready (English only at launch).
- **API client:** generated from FastAPI's OpenAPI schema (e.g. `@hey-api/openapi-ts` or `openapi-typescript`) into `apps/web/lib/api`. Regenerate in CI; fail CI if out of date. Note: the *public* OpenAPI must exclude Vault/admin routes — generate the web client from an internal schema endpoint available only in build/CI.
- **Routes:**
  - `/` home (search box over all tools, categories, popular tools), `/pricing`, `/c/[category]`, `/tools/[slug]`, `/jobs/[id]`
  - `/login`, `/signup`, `/auth/callback/*`, `/auth/magic`, `/auth/reset`
  - `/account` (profile, security/2FA, sessions), `/account/billing`, `/account/history`, `/account/api-keys`, `/account/credits`
  - `/admin/*` (admin+), `/vault/*` (super_admin; 404 otherwise, determined server-side before rendering)
  - `/developers` (public API docs, Phase 8), `/legal/terms`, `/legal/privacy`, `/legal/dmca`, `/legal/acceptable-use`
  - `/q/[code]` is handled by the **API** (fast redirect), not Next.js.
- **Generic tool runner** (`components/tool-runner`): dropzone uploader (multi-file, presigned multipart, progress, client-side type/size checks) → options form from JSON Schema → submit → SSE progress → result preview (PDF/image/audio/video/text viewers) → download / download ZIP → paywall modal on 402.
- **Custom tool UIs** (manifest `ui="custom"`): PDF editor & e-sign (pdf.js + pdf-lib), page organizer, video trimmer, invoice builder, resume builder, QR designer, uptime dashboard, chat-with-PDF chat UI, watermark mask brush (Vault).
- **SEO (critical for freemium traffic):** each tool page statically generated with title/description/H1, "how to" steps, FAQ, related tools, JSON-LD (`SoftwareApplication`, `HowTo`, `FAQPage`), canonical URLs, Open Graph images; `sitemap.xml` and `robots.txt` built from **public** manifests only; Core Web Vitals budget (LCP < 2.5 s). Tool content copy can be drafted with AI but must be reviewed for accuracy.
- **Design:** clean, fast, mobile-first, light/dark themes, accessible (WCAG 2.1 AA), no dark patterns in the paywall. Owner has not supplied branding yet (Q8) — use neutral design tokens that are easy to re-theme.
- **Analytics:** privacy-friendly, cookieless (self-hosted **Umami** or Plausible) so no cookie banner is required; track tool views, job submits, paywall shown/clicked, conversions. Never track Vault usage.
- **Ads:** none at launch (Q6).

## 16. Security, abuse prevention & legal

- **Input files:** size limits per level enforced at presign *and* in worker; magic-byte type detection; reject archives with excessive ratio/entries (zip-bomb guard); image decompression-bomb limits (Pillow `MAX_IMAGE_PIXELS`); PDF page caps per level.
- **Sandboxing converters:** LibreOffice, ffmpeg, Ghostscript-like tools, Chromium/Lighthouse run in the `cpu.sandbox`/`cpu.heavy` worker images as non-root, read-only root FS, `no-new-privileges`, dropped capabilities, seccomp default, CPU/memory/pids limits, per-job timeouts, temp dirs wiped after each job. Subprocesses get no network where feasible.
- **SSRF-safe fetcher** (`rendercart.safety.fetch`) for every server-side URL fetch (summarize URL, uptime, SSL, SEO audit, QR target validation, Vault downloaders): http/https only, resolve DNS and block private/loopback/link-local/CGNAT/multicast/metadata ranges (IPv4 + IPv6), pin the resolved IP for the connection, re-check on every redirect (max 5), response size + time caps. Start from `git show 4f1229f:image-service/url_safety.py` and its tests.
- **Abuse:** Cloudflare Turnstile for guest job submission and signup; per-IP and per-user rate limits (Redis); concurrency caps; ban/disable controls in admin; abuse report form; Google Safe Browsing / URLhaus checks for dynamic QR targets with periodic re-checks.
- **Web security:** strict CSP (nonce-based), HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`; downloads served with `Content-Disposition: attachment` from presigned URLs; never render user-uploaded HTML/SVG inline on the main origin.
- **Secrets:** `.env` files never committed; `.env.example` documents every variable; production secrets on the server with restricted permissions (later: sops/age or a secrets manager). Encrypt TOTP secrets at rest (app-level key).
- **Dependencies:** Renovate/Dependabot, `pip-audit`/`uv` audit and `pnpm audit` in CI, container image scanning (Trivy).
- **Privacy & legal pages:** Terms of Service, Privacy Policy (file retention, auto-deletion, third-party AI processing via OpenRouter, Stripe, analytics), Acceptable Use Policy, DMCA/takedown process, refund policy. Owner must supply the legal entity name and jurisdiction (Q4). Pages are templates until a lawyer reviews them.
- **Vault isolation:** see [§5.3](#53-the-vault-restricted-tools). Vault never appears in public artifacts (sitemap, OpenAPI, bundles, analytics).
- **Licenses:** maintain `docs/licenses.md`; CI check (e.g. `pip-licenses`, `license-checker`) that fails on AGPL/GPL/non-commercial in public code paths unless allow-listed with an ADR.

## 17. Infrastructure, DevOps & observability

### 17.1 Environments

| Env | Where | Notes |
|---|---|---|
| Local dev | Owner's Windows 11 machine, Docker Desktop + WSL2 | `just dev` brings up everything; `AI_MODE=mock` by default; Mailpit at :8025; stripe-cli forwards webhooks |
| Production | VPS (provider TBD, Q2) + GPU server(s) | Docker Compose; Tailscale/WireGuard private network; Caddy auto-TLS |
| Staging (optional, later) | Same VPS, separate compose project + subdomain | Stripe test mode |

Suggested starting VPS: 8 vCPU / 16–32 GB RAM / NVMe ≥ 200 GB. Scale out by adding CPU-worker-only VPSs.

### 17.2 Containers

`caddy`, `web`, `api`, `worker-cpu`, `worker-heavy`, `worker-sandbox`, `scheduler` (celery beat), `postgres` (with pgvector), `redis`, `minio`, `umami` (+ its DB), `prometheus`, `grafana`, `loki` (optional), `flower` (admin-only behind auth). GPU server: `worker-gpu` (×GPUs), `vllm`, `dcgm-exporter`, `node-exporter`.

### 17.3 Environment variables (`.env.example` must list all, with comments)

`APP_ENV`, `APP_BASE_URL`, `SECRET_KEY`, `ENCRYPTION_KEY`, `SUPER_ADMIN_EMAIL`, `DATABASE_URL`, `REDIS_URL`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET_UPLOADS`, `S3_BUCKET_RESULTS`, `S3_BUCKET_PERSISTENT`, `S3_BUCKET_VAULT`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `EMAIL_PROVIDER`, `RESEND_API_KEY`, `EMAIL_FROM`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO_MONTHLY`, `STRIPE_PRICE_DAY_PASS`, `STRIPE_PRICE_JOB_S/M/L`, `STRIPE_PRICE_CREDITS_500/1500`, `STRIPE_TAX_ENABLED`, `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `AI_MODE`, `VLLM_BASE_URL`, `VLLM_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MONTHLY_CAP_USD`, `GOOGLE_SAFE_BROWSING_KEY`, `MAXMIND_LICENSE_KEY`, `SENTRY_DSN`, `TWILIO_*` (later), `RETENTION_GUEST_MIN`, `RETENTION_FREE_MIN`, `RETENTION_PRO_MIN`.

### 17.4 CI/CD (GitHub Actions)

- **backend:** `uv sync` → `ruff check` + `ruff format --check` → `mypy` (or pyright) strict on `core/`, `auth/`, `billing/`, `registry/` → `pytest` with Postgres/Redis/MinIO service containers → coverage report.
- **web:** `pnpm install` → eslint → `tsc --noEmit` → vitest → `next build` → API client up-to-date check.
- **e2e:** Playwright against `docker compose` stack with `AI_MODE=mock` (on PRs to `main`, nightly).
- **security:** pip-audit, pnpm audit, Trivy image scan, license check.
- **release:** on `main`, build & push images to GHCR tagged by SHA; deploy job (manual approval) SSHes to VPS → `docker compose pull && docker compose up -d` → run Alembic migrations → smoke test. Separate workflow/runbook for GPU server.

### 17.5 Observability

- Structured JSON logs (`structlog`) with request id + job id correlation.
- **Sentry** for web (client + server) and backend (API + workers).
- **Prometheus + Grafana:** API latency/error rates, queue depth per queue, job duration/failure per tool, GPU utilization/VRAM, AI fallback rate, OpenRouter spend, Stripe revenue (synced), signups/conversions.
- **Alerts** (to owner's Discord webhook or email): API down, queue depth high, GPU node down, job failure spike, webhook failures, disk > 80%, backup failure, OpenRouter cap reached.
- Dogfood: use RenderCart's own uptime monitor on the production site.

### 17.6 Backups

Nightly `pg_dump` (compressed, encrypted) + `persistent` bucket sync to off-site storage (e.g. Backblaze B2 or Cloudflare R2); keep 14 daily + 8 weekly; **monthly restore test** documented in `docs/runbooks/backup-restore.md`. `uploads`/`results` are ephemeral and not backed up.

## 18. Build phases with acceptance criteria

Phases are sequential through Phase 2 (they build the platform). **After Phase 2, Phases 3–8 are largely independent** (each is a set of tool modules + maybe a custom UI) and can be built in parallel by separate agents on separate branches, provided they don't edit the same shared files without coordination.

### Phase 0 — Foundation
- Monorepo skeleton per [§8](#8-repository-layout); uv workspace; pnpm workspace; Next.js app boots; FastAPI app boots with `/api/health`.
- `infra/compose.yml` + `compose.dev.yml`: caddy, web, api, worker-cpu, scheduler, postgres+pgvector, redis, minio (buckets auto-created), mailpit, stripe-cli (profile).
- `justfile` with `dev`, `test`, `lint`, `fmt`, `migrate`, `gen-api` (must work from Windows via Git Bash/PowerShell).
- pydantic-settings config, structlog logging, Sentry hooks (no-op without DSN), Alembic initialized.
- ruff/mypy/pytest, eslint/tsc/vitest configured; GitHub Actions CI green.
- `.env.example`, `README.md` (quick start), `docs/adr/0001-stack.md` capturing [§3](#3-locked-decisions-do-not-re-litigate), `docs/licenses.md` started.
- **Done when:** `just dev` on a clean Windows machine serves the Next.js home page at `https://localhost` (or http) with `/api/health` returning OK through Caddy, and CI passes.

### Phase 1 — Core platform
- Auth: all four sign-in methods, sessions, CSRF, email verification, password reset, TOTP 2FA, rate limits, Mailpit-tested emails.
- Access levels & RBAC per [§5](#5-access-control-rbac--the-restricted-vault); `rendercart admin promote` CLI; super admin bootstrap; audit log.
- Tool registry + manifest validation + `GET /api/tools[/{slug}]` + `tool_overrides`.
- Job pipeline per [§10](#10-job-pipeline--file-lifecycle): presigned uploads, job creation, quotas (Redis Lua), Celery queues, SSE progress, downloads, retention cleanup, guest ownership via cookie, Turnstile.
- Credits ledger (holds/spend/release) — billing grants come in Phase 2, but admin grants work now.
- Frontend: auth pages, account pages, generic tool runner, job page, tool directory + search, category pages, paywall modal (wired to stub).
- **Two reference tools** to prove the pipeline end to end: `merge-pdf` (cpu) and `image-converter` (cpu). Plus 5 client-side tools (word counter, JSON formatter, QR static, Base64, password generator) to prove the client-tool registry.
- Security baseline: headers, CSP, safe fetcher module ported from old `url_safety.py` with tests.
- **Done when:** a guest can merge PDFs within limits, hits the paywall on the 3rd attempt, signs up with each auth method, sees history; a non-super-admin gets 404 on `/vault` and `/api/vault/*`; all registry invariant tests pass.

### Phase 2 — Billing
- Stripe products sync script; Checkout for Pro, day pass, single job (both flows), credit packs; Customer Portal; webhooks per [§14.3](#143-webhooks-post-apibillingwebhook) with idempotency; monthly credit grants; entitlement computation; billing page; admin comp/refund tools.
- **Done when:** in Stripe test mode, every purchase type grants the right entitlement only after the webhook, cancellation downgrades at period end, failed jobs refund credits, and duplicate webhook deliveries are no-ops (tests included).

### Phase 3 — PDF Suite ([§6.1](#61-category-a--pdf-suite-proven-earner))
- All PDF tools; sandbox worker for LibreOffice; custom UIs for organizer, editor, e-sign; batch mode; ADR on AGPL avoidance / PDF→Word approach.
- **Done when:** each tool has golden-file tests, free/pro limits enforced, editor/e-sign work in Chrome/Firefox/Safari, SEO pages live.

### Phase 4 — AI gateway + GPU workers + AI Image Studio ([§11](#11-ai-gateway--gpu-workers), [§6.2](#62-category-b--ai-image-studio))
- `infra/gpu/compose.gpu.yml`, Tailscale/WireGuard runbook, GPU worker image (CUDA base), model cache volume, LRU model manager, priority queues, high-demand handling.
- AI gateway with vLLM primary + OpenRouter fallback, health checks, circuit breaker, `ai_usage`, spend cap, `AI_MODE=mock|local-cpu|remote`.
- All Image Studio tools incl. preview-then-pay for background removal and product photos.
- **Done when:** jobs route to the GPU server, survive a GPU worker restart (task retry), LLM calls fall back to OpenRouter when vLLM is stopped, and the admin dashboard shows GPU/fallback metrics.

### Phase 5 — Audio & Video Studio ([§6.3](#63-category-c--audio--video-studio-user-uploaded-files-only--no-platform-downloading))
- Transcription (+diarization), subtitles (+translation), stems, TTS, denoise, video/audio converters, compressor, trimmer UI.
- **Done when:** a 60-minute file transcribes with progress updates and correct credit metering; 2 GB upload works for Pro via multipart.

### Phase 6 — AI Writing ([§6.4](#64-category-d--ai-writing--summaries))
- Summarizer (text/PDF/URL), chat-with-PDF (pgvector, citations), paraphraser, grammar, document translator, writing helpers.
- **Done when:** chat-with-PDF answers cite correct pages on a 200-page test doc; URL summarizer rejects internal-network URLs.

### Phase 7 — Business Generators ([§6.5](#65-category-e--business-generators))
- Invoice builder (saved clients, recurring), resume builder (+AI rewrite), dynamic QR with analytics + abuse gating, barcode, email signature, business cards.
- **Done when:** a dynamic QR's target can be edited without changing the printed code, scans are recorded with country/device, and a Safe-Browsing-flagged target is rejected.

### Phase 8 — Developer & Website Tools + Public API ([§6.6](#66-category-f--developer--website-tools))
- Uptime monitors, SSL/domain alerts, SEO/speed audit, webhook tester, API keys, public `/v1` API for public tools with credit billing and rate limits, `/developers` docs (public OpenAPI excluding admin/Vault).
- **Done when:** a monitor alerts via email + Discord within 2 checks of an outage; an API key can run `merge-pdf` and is billed correctly; Vault endpoints are absent from the public OpenAPI.

### Phase 9 — Vault & Admin dashboard ([§5.3](#53-the-vault-restricted-tools))
- Admin dashboard: users (search, plan, credits, ban, role for super_admin), jobs/queues, revenue, AI/GPU, tool flags & limits editor (`tool_overrides`), abuse reports, audit log.
- Vault tools: social downloaders (yt-dlp), watermark remover (LaMa), PDF unlocker, URL shortener, pastebin, temp file share, face tools.
- **Vault invariant test suite:** 404 for every level below super_admin on every Vault route; absent from `/api/tools`, sitemap, search, public OpenAPI, analytics, and the non-vault JS bundles; audit log written for every action; TOTP required.
- **Done when:** all invariant tests pass and the owner has verified access personally.

### Phase 10 — Launch polish
- All client-side tools from [§6.7](#67-free-client-side-tools-traffic-magnets-zero-server-cost); SEO content for every public tool; legal pages; analytics (Umami); Lighthouse ≥ 90 on tool pages; load test (k6 or Locust) of job pipeline; backups + restore test; production deploy runbook; monitoring alerts live; Stripe live mode switch checklist.
- **Done when:** production is live on the owner's domain, a real $9.99 subscription works end to end, and the owner signs off.

## 19. How to work in this repo (rules for agents)

1. **Read this plan fully first.** Respect [§3 Locked decisions](#3-locked-decisions-do-not-re-litigate). If something in this plan is wrong or blocked, write an ADR in `docs/adr/NNNN-title.md` (context, decision, consequences) and flag it to the owner — don't silently diverge.
2. **Open questions ([§21](#21-open-questions-for-the-owner))** have documented defaults. Use the default and keep going unless the question blocks you; then ask the owner.
3. **Safety first:** anything that could get the owner in legal trouble is `restricted=True` (Vault) by default. Never make a Vault tool public without explicit owner approval in writing.
4. **Licenses:** verify every new dependency/model license and add it to `docs/licenses.md` before merging.
5. **Library versions:** use the latest stable versions at implementation time (this plan intentionally does not pin versions). Python ≥ 3.12 (owner previously used 3.13), Node current LTS, PostgreSQL ≥ 16, Redis ≥ 7.
6. **Git conventions (from repo history):**
   - Commit messages are prefixed with an uppercase tag: `ADDED: …`, `FIX: …`, `REMOVED: …` (use `CHANGED: …`, `DOCS: …`, `REFACTOR: …`, `TEST: …` as needed).
   - Branches: existing pattern is `Feature-N` (Feature-1 … Feature-5); `main` is the default/PR target; a `develop` branch also exists — confirm with the owner which to target before opening PRs.
   - Commit or push only when the owner asks.
7. **Owner's environment:** Windows 11, Docker Desktop. All scripts/commands must work on Windows (use `just`, Python scripts, or Docker; avoid bash-only Makefiles).
8. **Testing:** every tool ships with tests (fixtures in its own `tests/` folder). Cross-cutting tests for RBAC, billing, registry invariants, and Vault isolation must stay green.
9. **Keep this plan current:** update the [§20 Status tracker](#20-status-tracker) checkboxes in the same PR that completes the work.
10. **Parallel work:** after Phase 2, separate agents may take separate categories. Shared files (`registry/`, `jobs/`, `ai/`, migrations, `apps/web/components/tool-runner`) need coordination — one owner per shared file per wave; migrations must be rebased/renumbered carefully.

## 20. Status tracker

- [x] Old codebase removed (`527fa5e`)
- [x] Plan written (this document)
- [ ] **Phase 0** — Foundation
- [ ] **Phase 1** — Core platform (auth, RBAC, registry, jobs, credits, 2 reference tools, 5 client tools)
- [ ] **Phase 2** — Billing (Stripe)
- [ ] **Phase 3** — PDF Suite
- [ ] **Phase 4** — AI gateway, GPU workers, AI Image Studio
- [ ] **Phase 5** — Audio & Video Studio
- [ ] **Phase 6** — AI Writing
- [ ] **Phase 7** — Business Generators
- [ ] **Phase 8** — Developer & Website Tools + Public API
- [ ] **Phase 9** — Vault & Admin dashboard
- [ ] **Phase 10** — Launch polish & production

## 21. Open questions for the owner

Each has a **default** so work isn't blocked. Record the answer here (and in an ADR if it changes architecture).

| # | Question | Default until answered |
|---|---|---|
| Q1 | GPU server details: GPU model(s), VRAM, count, OS, location/network path to the VPS, Docker + NVIDIA Container Toolkit installed? | Assume 1× 24 GB GPU, Linux, Docker available, reachable via Tailscale. Size models accordingly |
| Q2 | VPS provider/size and the **domain name** | Develop locally; production config parameterized by `APP_BASE_URL` |
| Q3 | Transactional email provider | Resend (Mailpit in dev) |
| Q4 | Legal entity name, country/state, and whether to enable **Stripe Tax** | Stripe Tax off but supported via config; legal pages as templates with placeholders |
| Q5 | Accept AGPL components (PyMuPDF, Ghostscript) for better PDF quality — which would require open-sourcing the service — or avoid them? | **Avoid** AGPL in public tools |
| Q6 | Ads on the free tier? | No ads at launch |
| Q7 | Annual Pro plan (e.g. $79/yr)? | Not at launch |
| Q8 | Branding: logo, colors, fonts, tone | Neutral, easily re-themeable design tokens |
| Q9 | Allow guests (no account) to use tools? | Yes, with lower limits + Turnstile |
| Q10 | SMS uptime alerts (Twilio costs money per SMS) | Pro only, 1 credit per SMS, monthly cap |
| Q11 | Final free limits, credit costs, single-job tiers | Use the numbers in [§4](#4-business-model-pricing-credits-limits) and [§6](#6-tool-catalog); all editable in admin |
| Q12 | Which branch should PRs target, `main` or `develop`? | Ask before opening the first PR |

## 22. Glossary

- **Access level** — ordered permission level `guest < free < day_pass < pro < admin < super_admin`; combines stored staff role and billing-derived plan.
- **Vault** — super-admin-only area for legally risky tools; hidden and 404 to everyone else.
- **Manifest** — the Python declaration of a tool (slug, category, limits, credits, runtime, SEO…). The registry loads and validates all manifests.
- **Job** — one execution of a server-side tool; has states, inputs/outputs in MinIO, progress, retention.
- **Credits** — internal currency metering GPU/LLM-heavy work for Pro/day-pass users; tracked in `credit_ledger`.
- **Job tier (S/M/L)** — the one-time price ($0.99/$1.99/$2.99) to unlock a single job beyond free limits.
- **Preview-then-pay** — tool produces a free preview (low-res/watermarked) and locks the full result until payment.
- **AI gateway** — internal library routing LLM calls to own vLLM first and OpenRouter as fallback, with cost tracking.
- **Client-side tool** — runs entirely in the browser; free, unlimited, used to attract search traffic.
- **Safe fetcher** — SSRF-protected HTTP client for all server-side URL fetches.
