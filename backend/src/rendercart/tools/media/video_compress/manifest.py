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
from rendercart.tools.media.common import VIDEO_MIMES
from rendercart.tools.media.video_compress.run import Options, run

TOOL = ToolManifest(
    slug="video-compressor",
    name="Video Compressor",
    category=Category.AUDIO_VIDEO,
    summary="Reduce MP4 video size with selectable quality presets.",
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
    credit_cost_per_100_mb=1,
    single_job_price_cents=199,
    job_tier=JobTier.MEDIUM,
    timeout_s=1800,
    seo=SeoMeta(
        title="Video Compressor Online | RenderCart",
        description=(
            "Compress uploaded video files into smaller MP4s while choosing a quality preset."
        ),
        keywords=["video compressor", "compress mp4", "reduce video size"],
    ),
    options=Options,
    runner=run,
)
