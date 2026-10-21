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
from rendercart.tools.pdf.to_word.run import run


class PdfToWordOptions(BaseModel):
    pages: str = Field(
        default="",
        max_length=255,
        description="Comma-separated pages or ranges, such as 1, 3-5. Blank converts all pages.",
    )
    bill_credits: bool = Field(default=False, json_schema_extra={"internal": True})


TOOL = ToolManifest(
    slug="pdf-to-word",
    name="PDF to Word",
    category=Category.PDF,
    batchable=True,
    summary="Extract selectable PDF text into an editable Word document.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_HEAVY,
    inputs=FileInput(
        accept=["application/pdf"],
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=1, max_files=1, max_total_mb=10),
        Level.FREE: Limit(count_per_day=2, max_files=1, max_total_mb=10),
        Level.PRO: Limit(fair_use_per_hour=30, max_files=1, max_total_mb=500),
    },
    credit_cost_per_10_pages=1,
    single_job_price_cents=199,
    job_tier=JobTier.MEDIUM,
    timeout_s=600,
    seo=SeoMeta(
        title="Convert PDF to Word | RenderCart",
        description=(
            "Convert selectable PDF text into an editable Word document while keeping page order."
        ),
        keywords=["pdf to word", "pdf to docx", "convert pdf to word"],
        faq=[
            (
                "Does this preserve the original page layout?",
                "The converter extracts text in reading order. Complex layouts, images, and exact "
                "formatting may need adjustment in Word.",
            ),
            (
                "Can I convert a scanned PDF?",
                "Run OCR first to add selectable text to a scanned PDF, then convert it to Word.",
            ),
        ],
    ),
    options=PdfToWordOptions,
    runner=run,
)
