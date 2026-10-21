# ADR 0003: Convert Office documents in the sandbox worker

- **Status:** Accepted for the planned Office-to-PDF public tool; final production package notice audit remains a launch gate.
- **Date:** 2026-10-18

## Context

Phase 3 requires DOCX, XLSX, and PPTX to PDF conversion. Rendering those formats accurately requires a document engine. The public-tool license policy avoids AGPL/GPL code and requires dependency notices to be recorded. LibreOffice is distributed under MPL-2.0 and includes components with separate licenses and notices, potentially including LGPL/GPL components, so the exact Debian packages and their notices must be audited in the final image.

## Decision

Use Debian's LibreOffice Writer, Calc, and Impress packages only inside the existing non-root, resource-limited `worker-sandbox` image. Convert one macro-free OOXML document per job, use a unique temporary user profile, launch without a shell, enforce a hard timeout and validate the resulting PDF. Reject malformed or mismatched OOXML packages, archive bombs, VBA payloads, and external relationships before invoking LibreOffice. Attach the sandbox worker only to a Docker `internal` network alongside the Postgres, Redis, and MinIO services it needs, so it has no route to public internet destinations.

The tool does not accept legacy OLE documents or macro-enabled OOXML files. It is not exposed from the Vault. The sandbox worker cannot initiate internet fetches; input documents containing external OOXML relationships are rejected before conversion.

## Consequences

- The sandbox image is larger and Office conversions use the sandbox worker's CPU, memory, and process limits. The worker shares a private network only with Postgres, Redis, and MinIO so required job services remain reachable without general egress.
- The production image build must retain and inventory the exact package versions and license notices under `/usr/share/doc`; unresolved GPL/AGPL components must be reviewed before launch.
- Local execution and visual fidelity tests require an installed LibreOffice binary. Unit tests mock the process boundary; container integration tests remain required when Docker is available.
- Output fidelity depends on the source file's fonts and layout; the image includes common Liberation and DejaVu fonts but cannot guarantee pixel-identical Microsoft Office rendering.
