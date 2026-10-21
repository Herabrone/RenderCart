# ADR 0002: Public PDF library strategy

- **Status:** Accepted
- **Date:** 2026-10-18

## Context

The public PDF suite must support common file operations while avoiding libraries or binaries whose AGPL/GPL terms could force the hosted application to publish its source or otherwise conflict with the product's commercial model. Several popular PDF choices, including PyMuPDF and Ghostscript, are flagged for that reason in the product plan.

## Decision

- Use `pypdf` (BSD-3-Clause) for public structural PDF operations: merge, extract, rotate, lossless rewrite/compression, and password protection.
- Use `pdfplumber` (MIT) for table detection and `openpyxl` (MIT/Expat) to produce actual XLSX files.
- Use `pypdfium2` (Apache-2.0 OR BSD-3-Clause, with PDFium and third-party notices shipped by upstream) for page rasterization. Keep upstream notices with deployed artifacts as required.
- Do not use PyMuPDF/pdf2docx or Ghostscript in public workers without a later owner-approved licensing ADR.
- The compression tool only deduplicates PDF objects and compresses page content streams. It does not recompress embedded images, and makes no promise that every input file will become smaller.
- For PDF-to-Word and Office-to-PDF, evaluate an isolated LibreOffice sandbox separately; this ADR does not approve that worker's deployment or license obligations.

## Consequences

- Public tools use libraries compatible with the intended commercial deployment and the current runtime license list in `docs/licenses.md`.
- Image-heavy PDFs may see little reduction from the current lossless compression tool. Image recompression requires a separate implementation and license review.
- pypdfium2's binary distribution requires retaining its notices. The container build and eventual deployment packaging must be checked before launch.
- OCR, signatures, office conversions, complex editing, and batch orchestration remain separate Phase 3 work.
