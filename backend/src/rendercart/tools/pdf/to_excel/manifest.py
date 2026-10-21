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
from rendercart.tools.pdf.to_excel.run import run


class PdfToExcelOptions(BaseModel):
    pages: str = Field(
        default="",
        max_length=255,
        description="Comma-separated pages or ranges, such as 1, 3-5. Blank scans all pages.",
    )


TOOL = ToolManifest(
    slug="pdf-to-excel",
    name="PDF to Excel",
    category=Category.PDF,
    batchable=True,
    summary="Extract detected PDF tables into an Excel workbook.",
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
    credit_cost=1,
    single_job_price_cents=199,
    job_tier=JobTier.MEDIUM,
    timeout_s=600,
    seo=SeoMeta(
        title="Convert PDF Tables to Excel | RenderCart",
        description="Extract detected tables from PDF pages into an XLSX workbook.",
        keywords=["pdf to excel", "pdf table extraction", "pdf to xlsx"],
    ),
    options=PdfToExcelOptions,
    runner=run,
)
