from pydantic import BaseModel, Field

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
from rendercart.tools.writing.chat_pdf.run import prepare, run


class Options(BaseModel):
    max_pages: int | None = Field(default=None, json_schema_extra={"internal": True})


TOOL = ToolManifest(
    slug="chat-with-pdf",
    name="Chat with PDF",
    category=Category.WRITING,
    summary=(
        "Ask questions about a PDF and get answers grounded in retrieved passages with "
        "page citations."
    ),
    runtime=Runtime.GPU,
    queue=Queue.GPU_EMBED,
    inputs=FileInput(
        accept=["application/pdf"],
        min_files=1,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=1, max_files=1, max_total_mb=10, max_pages=100),
        Level.FREE: Limit(count_per_day=1, max_files=1, max_total_mb=10, max_pages=100),
        Level.DAY_PASS: Limit(fair_use_per_hour=20, max_files=1, max_total_mb=500, max_pages=2_000),
        Level.PRO: Limit(
            fair_use_per_hour=20, max_files=1, max_total_mb=500, max_pages=2_000
        ),
        Level.ADMIN: Limit(
            fair_use_per_hour=20, max_files=1, max_total_mb=500, max_pages=2_000
        ),
        Level.SUPER_ADMIN: Limit(
            fair_use_per_hour=20, max_files=1, max_total_mb=500, max_pages=2_000
        ),
    },
    credit_cost=5,
    single_job_price_cents=199,
    job_tier=JobTier.MEDIUM,
    timeout_s=7_200,
    seo=SeoMeta(
        title="Chat with a PDF | Ask Questions and Get Page Citations",
        description=(
            "Upload a PDF, ask questions about its contents, and get grounded answers with "
            "page citations."
        ),
        keywords=["chat with PDF", "ask questions about PDF", "PDF AI assistant"],
    ),
    options=Options,
    runner=run,
    prepare=prepare,
)
