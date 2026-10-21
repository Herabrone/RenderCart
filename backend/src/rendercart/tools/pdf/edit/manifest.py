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
from rendercart.tools.pdf.edit.run import run


class EditOptions(BaseModel):
    preview: bool = Field(default=True, json_schema_extra={"internal": True})


TOOL = ToolManifest(
    slug="edit-pdf",
    name="Edit PDF",
    category=Category.PDF,
    summary="Add text and images, annotate pages, and fill interactive PDF form fields.",
    ui="custom",
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    inputs=FileInput(
        accept=["application/pdf"],
        min_files=1,
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 1},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=1, max_files=1, max_total_mb=10),
        Level.FREE: Limit(count_per_day=3, max_files=1, max_total_mb=10),
        Level.PRO: Limit(fair_use_per_hour=30, max_files=1, max_total_mb=500),
    },
    credit_cost=0,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    preview_then_pay=True,
    timeout_s=300,
    seo=SeoMeta(
        title="Edit PDF Online | RenderCart",
        description=(
            "Add text and images, annotate pages, and fill PDF forms. Free downloads include a "
            "RenderCart preview watermark; Pro and one-time unlocks provide clean PDFs."
        ),
        keywords=["edit pdf", "fill pdf form", "annotate pdf", "add text to pdf"],
        faq=[
            (
                "Can I change existing PDF text?",
                "This editor adds text and images over a page and fills interactive form fields. "
                "It does not rewrite text already printed into the PDF page content.",
            ),
            (
                "Why is my free download watermarked?",
                "Free downloads are marked as previews. Pro and one-time unlocks provide the "
                "clean edited PDF.",
            ),
        ],
    ),
    options=EditOptions,
    runner=run,
)
