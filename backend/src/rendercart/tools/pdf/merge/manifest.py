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
from rendercart.tools.pdf.merge.run import run


class MergeOptions(BaseModel):
    bookmark_title: str | None = Field(default=None, max_length=120)


TOOL = ToolManifest(
    slug="merge-pdf",
    name="Merge PDF",
    category=Category.PDF,
    batchable=True,
    summary="Combine PDF files into a single document.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    inputs=FileInput(
        accept=["application/pdf"],
        min_files=2,
        max_files={Level.GUEST: 5, Level.FREE: 5, Level.PRO: 50},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=2, max_files=5, max_total_mb=10),
        Level.FREE: Limit(count_per_day=3, max_files=5, max_total_mb=10),
        Level.PRO: Limit(fair_use_per_hour=120, max_files=50, max_total_mb=500),
    },
    credit_cost=0,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    seo=SeoMeta(
        title="Merge PDF Online — Free PDF Combiner | RenderCart",
        description="Combine PDF files into one document with RenderCart.",
        faq=[("Is it free?", "Free daily limits are planned; limits are configurable.")],
        keywords=["merge pdf", "combine pdf"],
    ),
    options=MergeOptions,
    runner=run,
)
