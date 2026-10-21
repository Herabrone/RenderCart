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
from rendercart.tools.pdf.protect.run import run


class ProtectOptions(BaseModel):
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Password required to open the protected PDF.",
        json_schema_extra={"sensitive": True, "format": "password"},
    )


TOOL = ToolManifest(
    slug="protect-pdf",
    name="Protect PDF",
    category=Category.PDF,
    batchable=True,
    summary="Encrypt a PDF with a password required to open it.",
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
        title="Add Password to PDF | RenderCart",
        description="Protect a PDF with strong AES-256 password encryption.",
        keywords=["protect pdf", "password protect pdf"],
    ),
    options=ProtectOptions,
    runner=run,
)
