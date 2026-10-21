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
from rendercart.tools.media.audio_denoise.run import Options, run
from rendercart.tools.media.common import AUDIO_MIMES

TOOL = ToolManifest(
    slug="audio-noise-reduction",
    name="Audio Noise Reduction",
    category=Category.AUDIO_VIDEO,
    summary=(
        "Reduce steady background hiss and room noise in an uploaded audio recording. "
        "Choose the strength and export MP3 or WAV."
    ),
    runtime=Runtime.CPU,
    queue=Queue.CPU_SANDBOX,
    inputs=FileInput(
        accept=AUDIO_MIMES,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 100, Level.FREE: 100, Level.PRO: 2048},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=1, max_files=1, max_total_mb=100),
        Level.FREE: Limit(count_per_day=1, max_files=1, max_total_mb=100),
        Level.DAY_PASS: Limit(fair_use_per_hour=10, max_files=1, max_total_mb=2048),
        Level.PRO: Limit(fair_use_per_hour=10, max_files=1, max_total_mb=2048),
        Level.ADMIN: Limit(fair_use_per_hour=10, max_files=1, max_total_mb=2048),
        Level.SUPER_ADMIN: Limit(fair_use_per_hour=10, max_files=1, max_total_mb=2048),
    },
    credit_cost=0,
    credit_cost_per_10_minutes=2,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=32_400,
    seo=SeoMeta(
        title="Reduce Audio Noise Online | RenderCart",
        description=(
            "Reduce steady background noise in audio recordings and export a clean MP3 or WAV."
        ),
        keywords=["audio noise reduction", "remove background noise", "audio denoiser"],
    ),
    options=Options,
    runner=run,
)
