# ADR 0005: Persisted Chat-with-PDF retrieval

- Status: Accepted
- Date: 2026-10-18

## Context

Phase 6 calls for Chat-with-PDF backed by page-aware chunking, BGE-M3 embeddings, pgvector retrieval, an LLM answer, and page citations. Indexing and questions need the existing owner-scoped job pipeline, credit holds, guest quotas, and file-retention model. Embeddings are not covered by OpenRouter, so they use the configured local OpenAI-compatible embedding endpoint and do not silently fall back to another provider.

## Decision

- Use the MIT-licensed BGE-M3 model by default and store 1024-dimensional vectors in PostgreSQL through pgvector. Serve it from a dedicated vLLM pooling endpoint, separately configurable with `AI_LOCAL_EMBEDDING_BASE_URL`; operators can select the served model through `AI_LOCAL_EMBEDDING_MODEL`, but it must return the configured 1024 dimensions. OpenRouter is not used for embeddings.
- Add persistent `chat_documents`, `document_chunks`, and `chat_turns` records. Preserve page numbers with every chunk; retrieve the nearest chunks by cosine distance and return page/excerpt citations alongside each answer.
- Index PDFs through the existing generic job pipeline on the GPU embedding queue. Charge five credits for an indexed document to day-pass/Pro users; guest/free users may retain one active document, receive one indexing job per day, and are limited to 100 pages per PDF.
- Run each question as a background job. Guest/free accounts receive ten questions per UTC day. Day-pass/Pro users hold and spend one credit per successful question; failed work releases its credit hold and free-tier quota reservation.
- Retain guest documents for 24 hours and free/day-pass documents for 30 days. Pro and staff documents remain until the owner deletes them. Deleting a document cascades to its chunks and chat history.
- Use retrieved excerpts and recent successful turns as context, instruct the model to treat source/history content as untrusted data, and return citations from the actual retrieved pages even if the model omits citation syntax.

## Consequences

- The PostgreSQL image must provide the pgvector extension; the migration enables it and creates an HNSW cosine index.
- The embedding server must return vectors of dimension 1024. Mock mode expands deterministic hashes to the same dimension for local flow development; it is not semantically meaningful retrieval.
- In `AI_MODE=mock`, indexing runs on the CPU-heavy queue so the feature can be developed in a local Compose environment without a GPU worker; production embedding remains on `gpu.embed`.
- The GPU Compose stack starts separate chat and BGE-M3 servers on ports 8000 and 8001. If the host cannot hold both models, run the embedding service on another GPU host and configure the embedding URL separately.
- Chat turns are durable independently of short-lived generic job records. Source files remain governed by upload retention; extracted text and vectors follow the document retention rules above.
- Page/excerpt citations identify retrieved source material and are not a guarantee that the LLM's natural-language claim is correct. The UI shows excerpts so users can inspect the cited evidence.
