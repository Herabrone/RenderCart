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
from rendercart.tools.media.common import AUDIO_MIMES, VIDEO_MIMES
from rendercart.tools.media.subtitle_generator.run import run


class Options(BaseModel):
    language: str | None = Field(
        default=None,
        max_length=3,
        pattern=r"^(?:[a-zA-Z]{2,3})?$",
        description="Optional language code, such as en or fr.",
    )
    output: Literal["srt", "vtt", "burn_in"] = Field(default="srt")
    font_size: int = Field(default=28, ge=18, le=48)
    font_color: Literal["white", "yellow", "cyan"] = Field(default="white")
    bill_credits: bool = Field(default=False, json_schema_extra={"internal": True})
    max_minutes_per_month: int | None = Field(default=None, json_schema_extra={"internal": True})


TOOL = ToolManifest(
    slug="subtitle-generator",
    name="Subtitle Generator",
    category=Category.AUDIO_VIDEO,
    summary="Create timed SRT or VTT subtitles from speech, or burn styled captions into video.",
    runtime=Runtime.GPU,
    queue=Queue.GPU_AUDIO,
    inputs=FileInput(
        accept=AUDIO_MIMES + VIDEO_MIMES,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 100, Level.FREE: 100, Level.PRO: 2048},
    ),
    limits={
        Level.GUEST: Limit(max_files=1, max_total_mb=100, max_minutes_per_month=3),
        Level.FREE: Limit(max_files=1, max_total_mb=100, max_minutes_per_month=10),
        Level.PRO: Limit(fair_use_per_hour=6, max_files=1, max_total_mb=2048),
    },
    credit_cost=0,
    credit_cost_per_minute=1,
    single_job_price_cents=199,
    job_tier=JobTier.MEDIUM,
    timeout_s=7200,
    seo=SeoMeta(
        title="Subtitle Generator Online | RenderCart",
        description=(
            "Generate SRT or VTT subtitles from audio and video, or burn captions into a video."
        ),
        keywords=["subtitle generator", "SRT generator", "VTT subtitles", "burn subtitles"],
    ),
    options=Options,
    runner=run,
)
