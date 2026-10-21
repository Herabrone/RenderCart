from typing import Literal

from pydantic import BaseModel, Field

from rendercart.core.access import Level
from rendercart.registry.models import (
    Category,
    FileInput,
    Limit,
    Queue,
    Runtime,
    SeoMeta,
    ToolManifest,
)
from rendercart.tools.media.common import SUBTITLE_MIMES
from rendercart.tools.media.subtitle_translation.run import run


class Options(BaseModel):
    target_language: Literal[
        "ar",
        "de",
        "en",
        "es",
        "fr",
        "hi",
        "it",
        "ja",
        "ko",
        "nl",
        "pl",
        "pt",
        "ru",
        "tr",
        "uk",
        "zh",
    ] = Field(description="Language for translated subtitles.")
    subtitle_format: Literal["srt", "vtt"] = Field(default="srt")
    bill_credits: bool = Field(default=False, json_schema_extra={"internal": True})


TOOL = ToolManifest(
    slug="subtitle-translation",
    name="Translate Subtitles",
    category=Category.AUDIO_VIDEO,
    summary=(
        "Translate an uploaded SRT or VTT subtitle file and preserve all original timecodes."
    ),
    min_level=Level.PRO,
    runtime=Runtime.LLM,
    queue=Queue.CPU_DEFAULT,
    inputs=FileInput(
        accept=SUBTITLE_MIMES,
        max_files={Level.PRO: 1},
        max_total_mb={Level.PRO: 10},
    ),
    limits={Level.PRO: Limit(fair_use_per_hour=6, max_files=1, max_total_mb=10)},
    credit_cost=0,
    credit_cost_per_minute=1,
    timeout_s=1800,
    seo=SeoMeta(
        title="Translate Video Subtitles Online | RenderCart",
        description=(
            "Translate SRT or VTT subtitles into another language while preserving their timing."
        ),
        keywords=["subtitle translation", "translate video subtitles", "translate SRT"],
    ),
    options=Options,
    runner=run,
)
