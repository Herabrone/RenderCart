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
from rendercart.tools.image.background_remover.run import run


class BackgroundRemovalOptions(BaseModel):
    preview: bool = Field(
        default=True,
        json_schema_extra={"internal": True},
    )


TOOL = ToolManifest(
    slug="background-remover",
    name="AI Background Remover",
    category=Category.IMAGE,
    summary="Remove an image background with a low-resolution preview for free accounts.",
    runtime=Runtime.GPU,
    queue=Queue.GPU_IMAGE,
    inputs=FileInput(
        accept=["image/jpeg", "image/png", "image/webp"],
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.DAY_PASS: 20, Level.PRO: 20},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.DAY_PASS: 500, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=1, max_files=1, max_total_mb=10),
        Level.FREE: Limit(count_per_day=1, max_files=1, max_total_mb=10),
        Level.DAY_PASS: Limit(fair_use_per_hour=30, max_files=20, max_total_mb=500),
        Level.PRO: Limit(fair_use_per_hour=30, max_files=20, max_total_mb=500),
    },
    credit_cost=2,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    preview_then_pay=True,
    timeout_s=600,
    seo=SeoMeta(
        title="AI Background Remover | RenderCart",
        description=(
            "Remove image backgrounds and download a transparent PNG. Free accounts get a "
            "small preview; Pro gets full resolution."
        ),
        keywords=["background remover", "remove image background", "transparent png"],
    ),
    options=BackgroundRemovalOptions,
    runner=run,
)
