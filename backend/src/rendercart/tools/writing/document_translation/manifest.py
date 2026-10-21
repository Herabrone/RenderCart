from typing import Literal

from pydantic import BaseModel, Field

from rendercart.core.access import Level
from rendercart.registry.models import (
    Category,
    FileInput,
    JobTier,
    Limit,
    Queue,
    Runtime,
    SeoMeta,
    ToolManifest,
)
from rendercart.tools.writing.document_translation.run import prepare, run


class Options(BaseModel):
    target_language: Literal[
        "ar",
        "de",
        "en",
        "es",
        "fr",
        "hi",
        "it",
        "ja",
        "ko",
        "nl",
        "pl",
        "pt",
        "ru",
        "tr",
        "uk",
        "zh",
    ] = Field(default="es", description="Language to translate the document into.")
    bill_credits: bool = Field(default=False, json_schema_extra={"internal": True})
    max_pages: int | None = Field(default=None, json_schema_extra={"internal": True})


TOOL = ToolManifest(
    slug="document-translator",
    name="Document Translator",
    category=Category.WRITING,
    summary=(
        "Translate PDF, Word, PowerPoint, and text documents while retaining the source format "
        "and document structure."
    ),
    runtime=Runtime.LLM,
    queue=Queue.CPU_HEAVY,
    inputs=FileInput(
        accept=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/plain",
        ],
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(max_files=1, max_total_mb=10, max_pages=1),
        Level.FREE: Limit(max_files=1, max_total_mb=10, max_pages=1),
        Level.DAY_PASS: Limit(fair_use_per_hour=6, max_files=1, max_total_mb=500, max_pages=2000),
        Level.PRO: Limit(fair_use_per_hour=6, max_files=1, max_total_mb=500, max_pages=2000),
        Level.ADMIN: Limit(fair_use_per_hour=6, max_files=1, max_total_mb=500, max_pages=2000),
        Level.SUPER_ADMIN: Limit(
            fair_use_per_hour=6, max_files=1, max_total_mb=500, max_pages=2000
        ),
    },
    credit_cost=0,
    credit_cost_per_page=2,
    single_job_price_cents=299,
    job_tier=JobTier.LARGE,
    timeout_s=7200,
    seo=SeoMeta(
        title="Translate Documents Online | RenderCart",
        description=(
            "Translate PDF, DOCX, PPTX, or TXT documents with AI while keeping the original "
            "file type and document structure."
        ),
        keywords=["document translator", "translate PDF", "translate DOCX", "translate PPTX"],
    ),
    options=Options,
    runner=run,
    prepare=prepare,
)
