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
from rendercart.tools.pdf.extract_pages.run import run


class ExtractPagesOptions(BaseModel):
    pages: str = Field(
        default="",
        max_length=255,
        description="Comma-separated pages or ranges, such as 1, 3-5. Blank keeps all pages.",
    )


TOOL = ToolManifest(
    slug="extract-pdf-pages",
    name="Extract PDF Pages",
    category=Category.PDF,
    batchable=True,
    summary="Select pages or page ranges and save them as a new PDF.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    inputs=FileInput(
        accept=["application/pdf"],
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=2, max_files=1, max_total_mb=10),
        Level.FREE: Limit(count_per_day=3, max_files=1, max_total_mb=10),
        Level.PRO: Limit(fair_use_per_hour=120, max_files=1, max_total_mb=500),
    },
    credit_cost=0,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    seo=SeoMeta(
        title="Extract Pages from PDF Online | RenderCart",
        description="Choose individual PDF pages or ranges and save them as a new PDF.",
        keywords=["extract pdf pages", "split pdf pages"],
    ),
    options=ExtractPagesOptions,
    runner=run,
)
