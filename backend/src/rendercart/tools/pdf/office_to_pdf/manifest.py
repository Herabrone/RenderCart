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
from rendercart.tools.pdf.office_to_pdf.run import run

_OFFICE_MIME_TYPES = [
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
]

TOOL = ToolManifest(
    slug="office-to-pdf",
    name="Word, Excel or PowerPoint to PDF",
    category=Category.PDF,
    batchable=True,
    summary="Convert DOCX, XLSX and PPTX files into a downloadable PDF.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_SANDBOX,
    inputs=FileInput(
        accept=_OFFICE_MIME_TYPES,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=2, max_files=1, max_total_mb=10),
        Level.FREE: Limit(count_per_day=3, max_files=1, max_total_mb=10),
        Level.PRO: Limit(fair_use_per_hour=60, max_files=1, max_total_mb=500),
    },
    credit_cost=0,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=300,
    seo=SeoMeta(
        title="Word, Excel and PowerPoint to PDF | RenderCart",
        description="Convert DOCX, XLSX and PPTX documents to PDF in a private sandbox.",
        keywords=["word to pdf", "excel to pdf", "powerpoint to pdf", "office to pdf"],
    ),
    runner=run,
)
