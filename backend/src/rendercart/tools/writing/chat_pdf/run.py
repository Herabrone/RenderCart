from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pdfplumber
from pydantic import BaseModel, Field

from rendercart.ai import AIError, gateway
from rendercart.ai.models import ChatDocument, DocumentChunk
from rendercart.auth.models import User
from rendercart.billing.access import user_level
from rendercart.core.access import Level
from rendercart.core.db import SessionLocal
from rendercart.jobs.models import Job, Upload
from rendercart.registry.models import ToolOutput, ToolPreparation

_MAX_SOURCE_CHARS = 20_000_000
_CHUNK_CHARS = 3_000
_EMBED_BATCH_SIZE = 32


class PreparedChunk(BaseModel):
    page_number: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=_CHUNK_CHARS)


def _split_page(text: str, page_number: int) -> list[PreparedChunk]:
    remaining = " ".join(text.split())
    chunks: list[PreparedChunk] = []
    overlap = 250
    while remaining:
        if len(remaining) <= _CHUNK_CHARS:
            piece = remaining
            remaining = ""
        else:
            boundary = remaining.rfind(" ", 0, _CHUNK_CHARS)
            if boundary < _CHUNK_CHARS // 2:
                boundary = _CHUNK_CHARS
            piece = remaining[:boundary].strip()
            remaining = remaining[max(boundary - overlap, 1) :].strip()
        if piece:
            chunks.append(PreparedChunk(page_number=page_number, content=piece))
    return chunks


def prepare(input_paths: list[Path], workdir: Path, options: dict[str, object]) -> ToolPreparation:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_pdf_required")
    page_limit = options.get("max_pages")
    max_pages = page_limit if isinstance(page_limit, int) and page_limit > 0 else 2_000
    chunks: list[PreparedChunk] = []
    total_chars = 0
    page_count = 0
    try:
        with pdfplumber.open(input_paths[0]) as document:
            if not document.pages or len(document.pages) > max_pages:
                raise ValueError("pdf_page_limit_exceeded")
            page_count = len(document.pages)
            for page_number, page in enumerate(document.pages, start=1):
                text = page.extract_text(layout=False) or ""
                total_chars += len(text)
                if total_chars > _MAX_SOURCE_CHARS:
                    raise ValueError("document_text_too_large")
                chunks.extend(_split_page(text, page_number))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("pdf_text_extraction_failed") from exc
    if not chunks:
        raise ValueError("pdf_contains_no_extractable_text")
    prepared_path = workdir / "document-chunks.json"
    prepared_path.write_text(
        json.dumps(
            {"page_count": page_count, "chunks": [chunk.model_dump() for chunk in chunks]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return ToolPreparation([prepared_path], word_count=sum(len(c.content.split()) for c in chunks))


def run(
    input_paths: list[Path],
    output_dir: Path,
    progress: Callable[[int], None] | None = None,
    job_id: UUID | None = None,
) -> ToolOutput:
    if len(input_paths) != 1 or job_id is None:
        raise ValueError("document_index_context_missing")
    try:
        raw_data = json.loads(input_paths[0].read_text(encoding="utf-8"))
        if not isinstance(raw_data, dict) or not isinstance(raw_data.get("chunks"), list):
            raise ValueError("invalid_chunk_data")
        page_count = int(raw_data.get("page_count", 0))
        chunks = [PreparedChunk.model_validate(item) for item in raw_data["chunks"]]
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("prepared_document_invalid") from exc
    if not chunks or page_count < 1:
        raise ValueError("pdf_contains_no_extractable_text")

    vectors: list[list[float]] = []
    for offset in range(0, len(chunks), _EMBED_BATCH_SIZE):
        batch = chunks[offset : offset + _EMBED_BATCH_SIZE]
        try:
            vectors.extend(
                gateway.embed(
                    [chunk.content for chunk in batch], task="document_indexing", job_id=job_id
                )
            )
        except AIError as exc:
            raise ValueError("embedding_unavailable") from exc
        if progress:
            progress(min(90, round((offset + len(batch)) / len(chunks) * 90)))
    if len(vectors) != len(chunks):
        raise ValueError("embedding_provider_returned_invalid_count")

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None or len(job.input_upload_ids) != 1:
            raise ValueError("indexing_job_not_found")
        upload = db.get(Upload, UUID(job.input_upload_ids[0]))
        if upload is None:
            raise ValueError("indexing_upload_not_found")
        if job.user_id:
            user = db.get(User, job.user_id)
            if user is None:
                raise ValueError("indexing_owner_not_found")
            level = user_level(db, user)
            expires_at = None if level >= Level.PRO else datetime.now(UTC) + timedelta(days=30)
        else:
            expires_at = datetime.now(UTC) + timedelta(hours=24)
        document = ChatDocument(
            id=uuid4(),
            user_id=job.user_id,
            guest_id=job.guest_id,
            indexed_job_id=job.id,
            filename=upload.filename,
            page_count=page_count,
            chunk_count=len(chunks),
            expires_at=expires_at,
        )
        db.add(document)
        db.flush()
        db.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    embedding=vector,
                )
                for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
            ]
        )
        db.commit()
        document_info = {
            "document_id": str(document.id),
            "filename": document.filename,
            "page_count": document.page_count,
            "chunk_count": document.chunk_count,
        }
    output = output_dir / "indexed-document.json"
    output.write_text(json.dumps(document_info), encoding="utf-8")
    if progress:
        progress(100)
    return ToolOutput(output, output.name, "application/json")
