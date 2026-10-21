from typing import Literal

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
from rendercart.tools.business.resume.run import run


class Options(BaseModel):
    resume_json: str = Field(
        min_length=2,
        max_length=24_000,
        title="Resume details",
        json_schema_extra={"internal": True, "sensitive": True},
    )
    template: Literal["classic", "modern", "compact"] = Field(
        default="classic",
        title="Resume layout",
        json_schema_extra={"internal": True},
    )
    rewrite_with_ai: bool = Field(
        default=False,
        title="Rewrite resume text with AI",
        description="Pro only; costs 2 credits and may need fact checking.",
        json_schema_extra={"internal": True},
    )
    branded: bool = Field(default=True, json_schema_extra={"internal": True})


TOOL = ToolManifest(
    slug="resume-builder",
    name="Resume and CV Builder",
    category=Category.BUSINESS,
    summary="Turn your experience and skills into a clean, downloadable resume PDF.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    inputs=FileInput(accept=[], min_files=0),
    limits={
        Level.GUEST: Limit(count_per_day=1),
        Level.FREE: Limit(count_per_day=1),
        Level.DAY_PASS: Limit(fair_use_per_hour=20),
        Level.PRO: Limit(fair_use_per_hour=20),
        Level.ADMIN: Limit(fair_use_per_hour=20),
        Level.SUPER_ADMIN: Limit(fair_use_per_hour=20),
    },
    credit_cost=None,
    single_job_price_cents=199,
    job_tier=JobTier.MEDIUM,
    timeout_s=300,
    seo=SeoMeta(
        title="Resume and CV Builder | RenderCart",
        description="Build a professional resume PDF from your experience, education, and skills.",
        keywords=["resume builder", "CV builder", "resume PDF"],
    ),
    options=Options,
    runner=run,
)
