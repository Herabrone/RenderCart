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
from rendercart.tools.pdf.from_images.run import run


class ImagesToPdfOptions(BaseModel):
    page_size: str = Field(
        default="image",
        pattern=r"^(image|a4|letter)$",
        description="Keep each image's dimensions or fit it onto A4 or Letter paper.",
    )
    orientation: str = Field(
        default="auto",
        pattern=r"^(auto|portrait|landscape)$",
        description="Choose each page's orientation when using a fixed page size.",
    )


TOOL = ToolManifest(
    slug="image-to-pdf",
    name="Images to PDF",
    category=Category.PDF,
    batchable=True,
    summary="Combine JPG or PNG images into a PDF, with optional A4 or Letter pages.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    inputs=FileInput(
        accept=["image/jpeg", "image/png"],
        max_files={Level.GUEST: 10, Level.FREE: 25, Level.PRO: 100},
        max_total_mb={Level.GUEST: 10, Level.FREE: 25, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=2, max_files=10, max_total_mb=10),
        Level.FREE: Limit(count_per_day=3, max_files=25, max_total_mb=25),
        Level.PRO: Limit(fair_use_per_hour=60, max_files=100, max_total_mb=500),
    },
    credit_cost=0,
    single_job_price_cents=99,
    job_tier=JobTier.SMALL,
    timeout_s=300,
    seo=SeoMeta(
        title="Convert Images to PDF | RenderCart",
        description="Combine JPG and PNG images into a single PDF with adjustable page sizing.",
        keywords=["jpg to pdf", "png to pdf", "images to pdf"],
    ),
    options=ImagesToPdfOptions,
    runner=run,
)
