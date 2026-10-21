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
from rendercart.tools.pdf.to_images.run import run


class PdfToImagesOptions(BaseModel):
    dpi: int = Field(default=150, ge=72, le=300, description="Image resolution (72–300 DPI).")


TOOL = ToolManifest(
    slug="pdf-to-images",
    name="PDF to JPG or PNG",
    category=Category.PDF,
    batchable=True,
    summary="Render PDF pages as crisp PNG images; multi-page files download as a ZIP.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_HEAVY,
    inputs=FileInput(
        accept=["application/pdf"],
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=2, max_files=1, max_total_mb=10),
        Level.FREE: Limit(count_per_day=3, max_files=1, max_total_mb=10),
        Level.PRO: Limit(fair_use_per_hour=30, max_files=1, max_total_mb=500),
    },
    credit_cost=0,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=600,
    seo=SeoMeta(
        title="Convert PDF Pages to PNG Images | RenderCart",
        description="Render every PDF page as a PNG image or download all pages in one ZIP.",
        keywords=["pdf to png", "convert pdf to image", "pdf to jpg"],
    ),
    options=PdfToImagesOptions,
    runner=run,
)
