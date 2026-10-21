from rendercart.core.access import Level
from rendercart.registry.models import (
    Category,
    FileInput,
    Limit,
    Queue,
    Runtime,
    SeoMeta,
    ToolManifest,
)
from rendercart.tools.writing.helper.run import Options, prepare, run

TOOL = ToolManifest(
    slug="writing-helper",
    name="AI Writing Helper",
    category=Category.WRITING,
    summary="Draft emails, titles, captions, product descriptions, social posts, and agendas.",
    runtime=Runtime.LLM,
    queue=Queue.CPU_HEAVY,
    inputs=FileInput(
        accept=["text/plain"],
        min_files=0,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=3),
        Level.FREE: Limit(count_per_day=3),
        Level.DAY_PASS: Limit(fair_use_per_hour=20),
        Level.PRO: Limit(fair_use_per_hour=20),
        Level.ADMIN: Limit(fair_use_per_hour=20),
        Level.SUPER_ADMIN: Limit(fair_use_per_hour=20),
    },
    credit_cost=1,
    timeout_s=180,
    seo=SeoMeta(
        title="AI Writing Helper | Draft Emails, Captions, and More",
        description=(
            "Generate a first draft for emails, titles, captions, product copy, and agendas."
        ),
        keywords=["AI email writer", "caption generator", "AI writing helper"],
    ),
    options=Options,
    runner=run,
    prepare=prepare,
)
