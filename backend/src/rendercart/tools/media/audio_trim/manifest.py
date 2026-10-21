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
from rendercart.tools.media.audio_trim.run import Options, run
from rendercart.tools.media.common import AUDIO_MIMES

TOOL = ToolManifest(
    slug="audio-trimmer",
    name="Audio Trimmer & Ringtone Maker",
    category=Category.AUDIO_VIDEO,
    summary="Choose a time range and save a short MP3 clip or ringtone.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_SANDBOX,
    inputs=FileInput(
        accept=AUDIO_MIMES,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 50, Level.FREE: 50, Level.PRO: 1000},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=3, max_files=1, max_total_mb=50),
        Level.FREE: Limit(count_per_day=10, max_files=1, max_total_mb=50),
        Level.PRO: Limit(fair_use_per_hour=30, max_files=1, max_total_mb=1000),
    },
    credit_cost=0,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=900,
    seo=SeoMeta(
        title="Audio Trimmer Online | RenderCart",
        description="Trim audio clips and create MP3 ringtones in your browser workflow.",
        keywords=["audio trimmer", "ringtone maker", "trim mp3"],
    ),
    options=Options,
    runner=run,
)
