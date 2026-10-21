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
from rendercart.tools.media.audio_extract.run import run
from rendercart.tools.media.common import VIDEO_MIMES

TOOL = ToolManifest(
    slug="audio-extractor",
    name="Extract Audio from Video",
    category=Category.AUDIO_VIDEO,
    summary="Extract the audio track from an uploaded video and save it as MP3.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_SANDBOX,
    inputs=FileInput(
        accept=VIDEO_MIMES,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 100, Level.FREE: 100, Level.PRO: 2048},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=2, max_files=1, max_total_mb=100),
        Level.FREE: Limit(count_per_day=5, max_files=1, max_total_mb=100),
        Level.PRO: Limit(fair_use_per_hour=15, max_files=1, max_total_mb=2048),
    },
    credit_cost=0,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=1800,
    seo=SeoMeta(
        title="Extract Audio from Video | RenderCart",
        description="Save the audio track from MP4, MOV, WebM, and other video uploads as MP3.",
        keywords=["extract audio from video", "video to mp3", "audio extractor"],
    ),
    runner=run,
)
