# Third-party licenses

Record every dependency and model used in RenderCart, its license, version, purpose, and whether it runs in public or Vault code. Verify licenses before adding runtime dependencies or model weights. Public tools must avoid AGPL/GPL and non-commercial components unless the owner approves an ADR.

| Component | License | Use | Scope | Verification |
|---|---|---|---|---|
| FastAPI | MIT | API | Public | 2026-10-17; upstream metadata |
| Pydantic | MIT | Settings and validation | Public | 2026-10-17; upstream metadata |
| SQLAlchemy | MIT | Database access | Public | 2026-10-17; upstream metadata |
| Structlog | MIT | Structured logging | Public | 2026-10-17; upstream metadata |
| pypdf | BSD-3-Clause | Merge PDF | Public | 2026-10-17; package metadata |
| ReportLab 5.0.1 | BSD-3-Clause | PDF editing previews, invoice/quote/receipt generation, business cards, and resume/CV output | Public | 2026-10-18; [official licensing FAQ](https://docs.reportlab.com/developerfaqs/) and [upstream license](https://github.com/MrBitBucket/reportlab-mirror/blob/master/LICENSE) |
| python-docx | MIT | Preserve DOCX structure while translating paragraph text | Public | 2026-10-18; [upstream project metadata](https://github.com/python-openxml/python-docx/blob/master/pyproject.toml) |
| python-pptx | MIT | Preserve PPTX slide structure while translating text frames and tables | Public | 2026-10-18; [upstream project metadata](https://github.com/scanny/python-pptx/blob/master/pyproject.toml) |
| FFmpeg (Debian package) | LGPL-2.1-or-later with optional GPL components depending on build configuration | Separate media processing executable for public audio/video conversion, trimming, extraction, denoising (`afftdn`), and compression | Sandboxed public worker | 2026-10-18; invoke as a separate binary; verify the production image's `ffmpeg -buildconf`, exact Debian package version, and `/usr/share/doc/ffmpeg/copyright` before release |
| pdfplumber | MIT | PDF table detection for XLSX export | Public | 2026-10-18; [upstream license](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt) |
| openpyxl | MIT/Expat | XLSX workbook generation for PDF table export | Public | 2026-10-18; [official documentation](https://openpyxl.readthedocs.io/en/stable/) |
| types-openpyxl | MIT | Static typing stubs for openpyxl | Development only | 2026-10-18; package metadata |
| pdfminer.six | MIT | PDF parsing dependency of pdfplumber | Public | 2026-10-18; [upstream license](https://github.com/pdfminer/pdfminer.six/blob/master/LICENSE) |
| Trafilatura 2.3.1 | Apache-2.0 | Main-content extraction for the public URL summarizer | Public CPU worker | 2026-10-18; [upstream license](https://github.com/adbar/trafilatura/blob/master/LICENSE); versions before 1.8.0 were GPLv3+, so keep the current Apache-2.0 version floor |
| Trafilatura runtime dependency closure (versions pinned in `backend/uv.lock`) | certifi MPL-2.0; charset-normalizer MIT; courlan and htmldate Apache-2.0; jusText BSD-2-Clause; lxml and lxml-html-clean BSD-3-Clause; dateparser and Babel BSD-3-Clause; pytz and six MIT; tld MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later (use the MPL-1.1 option); urllib3 MIT; python-dateutil Apache-2.0 OR BSD-3-Clause; regex Apache-2.0 AND CNRI-Python; tzlocal MIT; tzdata Apache-2.0 | URL summarizer extraction dependencies | Public CPU worker | 2026-10-18; package metadata from the resolved `uv.lock`; no GPL option is selected for `tld` |
| pgvector 0.5.1 | MIT | SQLAlchemy vector type and PostgreSQL vector search integration | Public | 2026-10-18; [upstream repository](https://github.com/pgvector/pgvector-python) |
| BGE-M3 (`BAAI/bge-m3`) | MIT | 1024-dimensional multilingual embeddings for Chat-with-PDF retrieval | Public GPU worker | 2026-10-18; [official model card/config](https://huggingface.co/BAAI/bge-m3) |
| pypdfium2 | Apache-2.0 OR BSD-3-Clause | PDF-to-image rendering and pdfplumber rendering | Public | 2026-10-18; [upstream licensing](https://github.com/pypdfium2-team/pypdfium2#licensing), PDFium binary third-party notices ship with its wheels |
| `pdfjs-dist` 6.4.299 | Apache-2.0 | Browser-side PDF page previews for the visual organizer | Public | 2026-10-18; package version is recorded in `apps/web/package.json` and `pnpm-lock.yaml`; Apache-2.0 verified from the package's `LICENSE` file |
| `pdf-lib` 1.17.1 | MIT | Browser-side visual PDF signature embedding | Public | 2026-10-18; package version is recorded in `apps/web/package.json` and `pnpm-lock.yaml`; MIT verified from the package's `LICENSE` file |
| `yaml` 2.9.1 | ISC | Browser-side JSON/YAML conversion | Public | 2026-10-18; [official package documentation](https://eemeli.org/yaml/) and [package license metadata](https://www.npmjs.com/package/yaml) |
| certifi 2026.10.18 | MPL-2.0 | Mozilla CA bundle for verified HTTPS requests to the ECB reference-rate feed | Public API/worker | 2026-10-18; [PyPI project metadata](https://pypi.org/project/certifi/2026.10.18/) |
| LibreOffice (Debian `libreoffice-writer`, `libreoffice-calc`, `libreoffice-impress`) | MPL-2.0; bundled third-party licenses vary and may include LGPL/GPL components | Sandboxed DOCX/XLSX/PPTX to PDF conversion | Public sandbox worker | 2026-10-18; [official licensing page](https://www.libreoffice.org/licenses/); retain the exact Debian package versions and `/usr/share/doc` notices from the production image |
| Tesseract OCR | Apache-2.0 | OCR text recognition and searchable PDF output in the sandbox worker | Public | 2026-10-18; [official repository license](https://github.com/tesseract-ocr/tesseract) and [official searchable-PDF documentation](https://tesseract-ocr.github.io/tessdoc/FAQ.html) |
| Tesseract trained data (English, German, French, Spanish) | Apache-2.0 | Language models used by the public OCR tool | Public | 2026-10-18; [official trained-data repository](https://github.com/tesseract-ocr/tessdata), [package/install notes](https://github.com/tesseract-ocr/tessdoc/blob/main/Installation.md) |
| Pillow | HPND | Image conversion | Public | 2026-10-17; package metadata |
| qrcode (npm) | MIT | Browser-side static QR generation | Public | 2026-10-18; package metadata |
| JsBarcode 3.12.3 | MIT | Browser-side Code 128 barcode generation | Public | 2026-10-18; [upstream repository](https://github.com/lindell/JsBarcode) |
| Celery | BSD-3-Clause | Job queue and scheduled cleanup | Public | 2026-10-18; package metadata |
| Lighthouse CLI 13.5.0 | Apache-2.0 | Sandboxed website performance, accessibility, best-practices, and SEO reports | Public audit worker | 2026-10-19; [upstream package metadata](https://github.com/GoogleChrome/lighthouse/blob/main/package.json); requires Node.js >=22.19 according to its upstream engine declaration |
| Node.js 22.19 | MIT plus externally maintained components | Lighthouse CLI runtime in the sandbox worker | Public audit worker | 2026-10-19; [upstream license](https://github.com/nodejs/node/blob/main/LICENSE) |
| Chromium (Debian package) | BSD-3-Clause plus bundled third-party licenses | Headless browser used by Lighthouse in the isolated worker | Public audit worker | 2026-10-19; retain the exact Debian package version and `/usr/share/doc/chromium/copyright` from the production image |
| redis-py | MIT | Atomic quotas, auth limits, and job progress | Public | 2026-10-18; package metadata |
| boto3 / botocore | Apache-2.0 | S3-compatible object storage | Public | 2026-10-18; package metadata |
| argon2-cffi | MIT | Password hashing | Public | 2026-10-17; package metadata |
| pyotp | MIT | TOTP two-factor authentication | Public | 2026-10-17; package metadata |
| cryptography | Apache-2.0 OR BSD-3-Clause | Encrypting TOTP secrets | Public | 2026-10-17; package metadata |
| Authlib | BSD-3-Clause | Google and GitHub OAuth 2.0 | Public | 2026-10-17; package metadata |
| HTTPX | BSD-3-Clause | OAuth provider API calls | Public | 2026-10-17; package metadata |
| HTTPX2 | BSD-3-Clause | Authlib HTTP client | Public | 2026-10-17; package metadata |
| itsdangerous | BSD-3-Clause | Signed OAuth state cookie | Public | 2026-10-17; package metadata |
| Stripe Python SDK | MIT | Checkout, billing portal, and signed webhook verification | Public | 2026-10-18; package metadata |
| vLLM | Apache-2.0 | OpenAI-compatible self-hosted LLM server | GPU infrastructure | 2026-10-18; [upstream license](https://github.com/vllm-project/vllm/blob/main/LICENSE) |
| PyTorch | BSD-3-Clause plus bundled third-party licenses | GPU worker runtime | GPU infrastructure | 2026-10-18; [upstream project license metadata](https://github.com/pytorch/pytorch/blob/main/pyproject.toml); audit the exact container's bundled notices before production |
| Transformers | Apache-2.0 | Load pinned BiRefNet model code and weights | GPU worker | 2026-10-18; upstream package metadata |
| Accelerate | Apache-2.0 | Model loading/runtime support | GPU worker | 2026-10-18; upstream package metadata |
| faster-whisper 1.2.1 | MIT | GPU speech-to-text inference for transcription | Public GPU tool | 2026-10-18; [upstream license](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) |
| faster-whisper-large-v3 (`Systran/faster-whisper-large-v3`, revision `edaa852ec7e145841d8ffdb056a99866b5f0a478`) | MIT | Pinned speech recognition model for transcription | Public GPU tool | 2026-10-18; [pinned model card](https://huggingface.co/Systran/faster-whisper-large-v3/tree/edaa852ec7e145841d8ffdb056a99866b5f0a478) |
| pyannote.audio 4.0.7 | MIT | Optional GPU speaker diarization inference | Public GPU tool | 2026-10-18; [upstream license](https://github.com/pyannote/pyannote-audio) |
| `pyannote/speaker-diarization-community-1` (revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee`) | CC-BY-4.0 | Optional speaker diarization model | Public GPU tool; requires owner HF account to accept model conditions and provide a token | 2026-10-18; [pinned model card and access conditions](https://huggingface.co/pyannote/speaker-diarization-community-1/tree/3533c8cf8e369892e6b79ff1bf80f7b0286a54ee); attribution is included in diarization output ZIP |
| Kokoro 0.9.4 | Apache-2.0 | GPU text-to-speech inference | Public GPU tool | 2026-10-18; [upstream repository and license](https://github.com/hexgrad/kokoro) |
| Kokoro-82M (`hexgrad/Kokoro-82M`, revision `c3327e9bac3dbe55779397bfa82de0f8806fb3bc`) | Apache-2.0 | Pinned text-to-speech weights and voice embeddings | Public GPU tool | 2026-10-18; [pinned model card](https://huggingface.co/hexgrad/Kokoro-82M/tree/c3327e9bac3dbe55779397bfa82de0f8806fb3bc) |
| Misaki 0.9.4 | Apache-2.0 | English grapheme-to-phoneme processing for text-to-speech (installed without the optional GPL phonemizer extra) | Public GPU tool | 2026-10-18; [upstream package metadata](https://github.com/hexgrad/misaki/blob/main/pyproject.toml) |
| en_core_web_sm 3.8.0 | MIT | English NLP pipeline used by Misaki G2P | Public GPU tool | 2026-10-18; [pinned upstream model metadata](https://github.com/explosion/spacy-models/blob/master/meta/en_core_web_sm-3.8.0.json) |
| SoundFile 0.14.0 | BSD-3-Clause | Streaming PCM WAV output for text-to-speech | Public GPU tool | 2026-10-18; package metadata |
| FFmpeg (GPU Debian package) | LGPL-2.1-or-later with optional GPL components depending on build configuration | ffprobe validation and optional WAV-to-MP3 encoding for GPU media tools | GPU worker | 2026-10-18; inspect exact GPU image `ffmpeg -buildconf`, package version, and copyright notices before release |
| BiRefNet (`ZhengPeng7/BiRefNet`, revision `e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4`) | MIT | Public image background removal | Public GPU tool | 2026-10-18; [pinned model card](https://huggingface.co/ZhengPeng7/BiRefNet/tree/e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4) and [upstream license](https://github.com/ZhengPeng7/BiRefNet/blob/main/LICENSE) |
| Next.js | MIT | Web application | Public | 2026-10-17; upstream metadata |
| Tailwind CSS | MIT | Styling | Public | 2026-10-17; upstream metadata |
