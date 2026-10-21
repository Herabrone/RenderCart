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
from rendercart.tools.media.transcription.run import Options, run

TOOL = ToolManifest(
    slug="transcription",
    name="Audio & Video Transcription",
    category=Category.AUDIO_VIDEO,
    summary=(
        "Transcribe speech into a plain-text transcript, SRT subtitles, and timestamped JSON, "
        "with optional speaker labels."
    ),
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
        title="Audio & Video Transcription Online | RenderCart",
        description=(
            "Transcribe speech from audio or video into text, SRT subtitles, and timestamped JSON."
        ),
        keywords=["audio transcription", "video transcription", "speech to text", "SRT subtitles"],
    ),
    options=Options,
    runner=run,
)
