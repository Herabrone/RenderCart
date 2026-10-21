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
from rendercart.tools.writing.paraphraser.run import Options, prepare, run

TOOL = ToolManifest(
    slug="paraphraser",
    name="AI Paraphraser",
    category=Category.WRITING,
    summary="Rewrite text in a chosen tone while keeping its meaning and key details.",
    runtime=Runtime.LLM,
    queue=Queue.CPU_HEAVY,
    inputs=FileInput(
        accept=["text/plain"],
        min_files=0,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
    ),
    limits={
        Level.GUEST: Limit(
            max_files=1, max_total_mb=1, max_words_per_job=500, word_count_per_day=500
        ),
        Level.FREE: Limit(
            max_files=1, max_total_mb=1, max_words_per_job=500, word_count_per_day=500
        ),
        Level.DAY_PASS: Limit(
            fair_use_per_hour=20, max_files=1, max_total_mb=1, max_words_per_job=10_000
        ),
        Level.PRO: Limit(
            fair_use_per_hour=20, max_files=1, max_total_mb=1, max_words_per_job=10_000
        ),
        Level.ADMIN: Limit(
            fair_use_per_hour=20, max_files=1, max_total_mb=1, max_words_per_job=10_000
        ),
        Level.SUPER_ADMIN: Limit(
            fair_use_per_hour=20, max_files=1, max_total_mb=1, max_words_per_job=10_000
        ),
    },
    credit_cost=0,
    credit_cost_per_1000_words=1,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=300,
    seo=SeoMeta(
        title="AI Paraphraser | Rewrite Text in Different Tones",
        description=(
            "Paraphrase text into a clear, professional, friendly, concise, or formal style."
        ),
        keywords=["AI paraphraser", "rewrite text", "paraphrase tool"],
    ),
    options=Options,
    runner=run,
    prepare=prepare,
)
