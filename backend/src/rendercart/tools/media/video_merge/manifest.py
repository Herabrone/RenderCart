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
from rendercart.tools.media.video_merge.run import run

TOOL = ToolManifest(
    slug="video-merger",
    name="Video Merger",
    category=Category.AUDIO_VIDEO,
    summary="Join multiple uploaded video clips into one MP4 in selection order.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_SANDBOX,
    inputs=FileInput(
        accept=VIDEO_MIMES,
        min_files=2,
        max_files={Level.GUEST: 2, Level.FREE: 3, Level.PRO: 10},
        max_total_mb={Level.GUEST: 100, Level.FREE: 100, Level.PRO: 2048},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=1, max_files=2, max_total_mb=100),
        Level.FREE: Limit(count_per_day=3, max_files=3, max_total_mb=100),
        Level.PRO: Limit(fair_use_per_hour=10, max_files=10, max_total_mb=2048),
    },
    credit_cost=0,
    single_job_price_cents=199,
    job_tier=JobTier.MEDIUM,
    timeout_s=3600,
    seo=SeoMeta(
        title="Video Merger Online | RenderCart",
        description="Join uploaded video clips into one MP4 in the order you select them.",
        keywords=["video merger", "merge videos", "join mp4 files"],
    ),
    runner=run,
)
