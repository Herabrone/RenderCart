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
from rendercart.tools.pdf.ocr.run import run


class OcrOptions(BaseModel):
    language: str = Field(
        default="eng",
        pattern="^(eng|deu|fra|spa)$",
        description="OCR language: English, German, French, or Spanish.",
    )
    dpi: int = Field(default=200, ge=100, le=300, description="Scan resolution (100–300 DPI).")
    max_pages: int = Field(default=1, ge=1, json_schema_extra={"internal": True})
    bill_credits: bool = Field(default=False, json_schema_extra={"internal": True})


TOOL = ToolManifest(
    slug="pdf-ocr",
    name="OCR PDF",
    category=Category.PDF,
    batchable=True,
    summary=(
        "Turn scanned PDF pages into searchable text while preserving existing text pages. "
        "Pro and day-pass OCR costs one credit per ten pages."
    ),
    runtime=Runtime.CPU,
    queue=Queue.CPU_SANDBOX,
    inputs=FileInput(
        accept=["application/pdf"],
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=1, max_files=1, max_total_mb=10, max_pages=1),
        Level.FREE: Limit(count_per_day=3, max_files=1, max_total_mb=10, max_pages=3),
        Level.DAY_PASS: Limit(fair_use_per_hour=20, max_files=1, max_total_mb=500, max_pages=200),
        Level.PRO: Limit(fair_use_per_hour=20, max_files=1, max_total_mb=500, max_pages=200),
    },
    credit_cost=0,
    credit_cost_per_10_pages=1,
    single_job_price_cents=199,
    job_tier=JobTier.MEDIUM,
    timeout_s=3600,
    seo=SeoMeta(
        title="OCR PDF Online — Make Scanned PDFs Searchable | RenderCart",
        description="Recognize text in scanned PDFs and download a searchable PDF copy.",
        keywords=["ocr pdf", "searchable pdf", "scan to text pdf"],
        faq=[
            (
                "Does OCR keep my original pages?",
                "Pages with existing text are preserved unchanged.",
            ),
            ("Which OCR languages are supported?", "English, German, French, and Spanish."),
        ],
    ),
    options=OcrOptions,
    runner=run,
)
