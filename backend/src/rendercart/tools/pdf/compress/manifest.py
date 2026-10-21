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
from rendercart.tools.pdf.compress.run import run


class CompressOptions(BaseModel):
    preset: str = Field(
        default="balanced",
        pattern="^(balanced|maximum)$",
        description="Lossless object cleanup preset.",
    )


TOOL = ToolManifest(
    slug="compress-pdf",
    name="Compress PDF",
    category=Category.PDF,
    batchable=True,
    summary=(
        "Optimize a PDF by removing duplicate objects and rewriting its structure "
        "without reducing image quality."
    ),
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
        title="Compress PDF Online | RenderCart",
        description="Optimize PDF structure without lowering image quality.",
        keywords=["compress pdf", "optimize pdf"],
    ),
    options=CompressOptions,
    runner=run,
)
