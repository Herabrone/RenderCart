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
from rendercart.tools.business.business_card.run import run


class Options(BaseModel):
    card_json: str = Field(
        min_length=2,
        max_length=8_000,
        title="Business card details",
        json_schema_extra={"internal": True, "sensitive": True},
    )
    branded: bool = Field(default=True, json_schema_extra={"internal": True})


TOOL = ToolManifest(
    slug="business-card",
    name="Business Card Generator",
    category=Category.BUSINESS,
    summary=(
        "Create a print-ready business card PDF with 0.125-inch bleed and trim marks."
    ),
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    inputs=FileInput(accept=[], min_files=0),
    limits={
        Level.GUEST: Limit(count_per_day=2),
        Level.FREE: Limit(count_per_day=5),
        Level.DAY_PASS: Limit(fair_use_per_hour=20),
        Level.PRO: Limit(fair_use_per_hour=20),
        Level.ADMIN: Limit(fair_use_per_hour=20),
        Level.SUPER_ADMIN: Limit(fair_use_per_hour=20),
    },
    credit_cost=None,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=300,
    seo=SeoMeta(
        title="Business Card Generator | RenderCart",
        description="Create a landscape business card PDF with bleed and trim marks for printing.",
        keywords=["business card maker", "business card PDF", "print-ready business cards"],
    ),
    options=Options,
    runner=run,
)
