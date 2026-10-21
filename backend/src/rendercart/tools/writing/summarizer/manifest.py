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
from rendercart.tools.writing.summarizer.run import Options, prepare, run

TOOL = ToolManifest(
    slug="summarizer",
    name="AI Summarizer",
    category=Category.WRITING,
    summary=(
        "Summarize pasted text, PDF or text documents, and public web pages into a concise, "
        "fact-focused summary."
    ),
    runtime=Runtime.LLM,
    queue=Queue.CPU_HEAVY,
    inputs=FileInput(
        accept=["application/pdf", "text/plain"],
        min_files=0,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=1, max_files=1, max_total_mb=10, max_words_per_job=5_000),
        Level.FREE: Limit(count_per_day=3, max_files=1, max_total_mb=10, max_words_per_job=5_000),
        Level.DAY_PASS: Limit(fair_use_per_hour=20, max_files=1, max_total_mb=500),
        Level.PRO: Limit(fair_use_per_hour=20, max_files=1, max_total_mb=500),
        Level.ADMIN: Limit(fair_use_per_hour=20, max_files=1, max_total_mb=500),
        Level.SUPER_ADMIN: Limit(fair_use_per_hour=20, max_files=1, max_total_mb=500),
    },
    credit_cost=2,
    credit_cost_per_10000_words=1,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=7_200,
    seo=SeoMeta(
        title="AI Text and PDF Summarizer | RenderCart",
        description=(
            "Summarize text, PDFs, and public web pages with clear, source-grounded AI summaries."
        ),
        keywords=["text summarizer", "PDF summarizer", "AI summarizer", "article summarizer"],
    ),
    options=Options,
    runner=run,
    prepare=prepare,
)
