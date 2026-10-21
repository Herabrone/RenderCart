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
from rendercart.tools.media.text_to_speech.run import Options, run

TOOL = ToolManifest(
    slug="text-to-speech",
    name="Text to Speech",
    category=Category.AUDIO_VIDEO,
    summary="Turn a text file into natural-sounding English speech in MP3 or WAV format.",
    runtime=Runtime.GPU,
    queue=Queue.GPU_AUDIO,
    inputs=FileInput(
        accept=["text/plain"],
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.DAY_PASS: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 1, Level.FREE: 1, Level.DAY_PASS: 1, Level.PRO: 1},
    ),
    limits={
        Level.GUEST: Limit(
            count_per_day=1, max_files=1, max_total_mb=1, max_characters_per_job=500
        ),
        Level.FREE: Limit(
            count_per_day=3, max_files=1, max_total_mb=1, max_characters_per_job=500
        ),
        Level.DAY_PASS: Limit(
            fair_use_per_hour=20, max_files=1, max_total_mb=1, max_characters_per_job=100_000
        ),
        Level.PRO: Limit(
            fair_use_per_hour=20, max_files=1, max_total_mb=1, max_characters_per_job=100_000
        ),
    },
    credit_cost=0,
    credit_cost_per_1000_chars=1,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=3600,
    seo=SeoMeta(
        title="Text to Speech MP3 Converter | RenderCart",
        description="Create English speech audio from text and download it as MP3 or WAV.",
        keywords=["text to speech", "text to mp3", "AI voice generator", "Kokoro TTS"],
    ),
    options=Options,
    runner=run,
)
