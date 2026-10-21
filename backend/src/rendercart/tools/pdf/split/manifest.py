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
from rendercart.tools.pdf.split.run import run


class SplitOptions(BaseModel):
    pages_per_file: int = Field(default=1, ge=1, le=100, description="Pages in each output PDF.")


TOOL = ToolManifest(
    slug="split-pdf",
    name="Split PDF",
    category=Category.PDF,
    batchable=True,
    summary="Split a PDF into page groups and download them together in a ZIP file.",
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
        title="Split PDF Pages Online | RenderCart",
        description="Split PDF pages into smaller documents, packaged as a ZIP download.",
        keywords=["split pdf", "separate pdf pages"],
    ),
    options=SplitOptions,
    runner=run,
)
