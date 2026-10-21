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
from rendercart.tools.media.audio_convert.run import Options, run
from rendercart.tools.media.common import AUDIO_MIMES

TOOL = ToolManifest(
    slug="audio-converter",
    name="Audio Converter",
    category=Category.AUDIO_VIDEO,
    summary="Convert audio files between MP3, WAV, FLAC, M4A, and OGG.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_SANDBOX,
    inputs=FileInput(
        accept=AUDIO_MIMES,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 20},
        max_total_mb={Level.GUEST: 50, Level.FREE: 50, Level.PRO: 1000},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=3, max_files=1, max_total_mb=50),
        Level.FREE: Limit(count_per_day=10, max_files=1, max_total_mb=50),
        Level.PRO: Limit(fair_use_per_hour=30, max_files=20, max_total_mb=1000),
    },
    credit_cost=0,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=900,
    seo=SeoMeta(
        title="Audio Converter Online | RenderCart",
        description="Convert audio to MP3, WAV, FLAC, M4A, or OGG with private, expiring uploads.",
        keywords=["audio converter", "mp3 converter", "wav converter", "flac converter"],
    ),
    options=Options,
    runner=run,
)
