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
from rendercart.tools.pdf.organize.run import run


class OrganizeOptions(BaseModel):
    page_order: str = Field(
        default="",
        max_length=10_000,
        description=(
            "Pages to keep, in output order; for example 3, 1, 2-4. Leave blank to keep all."
        ),
    )


TOOL = ToolManifest(
    slug="organize-pdf",
    name="Reorder or Remove PDF Pages",
    category=Category.PDF,
    batchable=True,
    summary="Choose the pages to keep and arrange them in the output order.",
    ui="custom",
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
        title="Reorder or Delete PDF Pages | RenderCart",
        description="Reorder PDF pages or remove unwanted pages and download the result.",
        keywords=["reorder pdf pages", "delete pdf pages", "organize pdf"],
    ),
    options=OrganizeOptions,
    runner=run,
)
