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
from rendercart.tools.media.video_trim.run import Options, run

TOOL = ToolManifest(
    slug="video-trimmer",
    name="Video Trimmer",
    category=Category.AUDIO_VIDEO,
    summary="Trim an uploaded video by choosing its start and end times.",
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
        title="Video Trimmer Online | RenderCart",
        description="Choose a start and end time to trim an uploaded video.",
        keywords=["video trimmer", "trim video", "cut video online"],
    ),
    options=Options,
    runner=run,
)
