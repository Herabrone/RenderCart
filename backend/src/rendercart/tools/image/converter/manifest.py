from pydantic import BaseModel, Field

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
from rendercart.tools.image.converter.run import run


class ImageConverterOptions(BaseModel):
    output_format: str = Field(pattern=r"^(PNG|JPEG|WEBP)$")


TOOL = ToolManifest(
    slug="image-converter",
    name="Image Converter",
    category=Category.IMAGE,
    summary="Convert images between PNG, JPEG, and WebP formats.",
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    inputs=FileInput(
        accept=["image/png", "image/jpeg", "image/webp"],
        max_files={Level.GUEST: 1, Level.FREE: 1, Level.PRO: 20},
        max_total_mb={Level.GUEST: 10, Level.FREE: 20, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_day=2, max_files=1, max_total_mb=10),
        Level.FREE: Limit(count_per_day=3, max_files=1, max_total_mb=20),
        Level.PRO: Limit(fair_use_per_hour=120, max_files=20, max_total_mb=500),
    },
    credit_cost=0,
    single_job_price_cents=99,
    seo=SeoMeta(
        title="Image Converter — PNG, JPG & WebP | RenderCart",
        description="Convert common image formats with RenderCart.",
        faq=[
            (
                "Which formats are supported?",
                "PNG, JPEG, and WebP are supported in the starter tool.",
            )
        ],
        keywords=["image converter", "png to jpg", "webp converter"],
    ),
    options=ImageConverterOptions,
    runner=run,
)
