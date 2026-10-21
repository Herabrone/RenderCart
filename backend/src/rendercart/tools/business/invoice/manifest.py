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
from rendercart.tools.business.invoice.run import run


class Options(BaseModel):
    invoice_json: str = Field(
        min_length=2,
        max_length=50_000,
        title="Invoice details",
        json_schema_extra={"internal": True, "sensitive": True},
    )
    branded: bool = Field(default=True, json_schema_extra={"internal": True})


TOOL = ToolManifest(
    slug="invoice-generator",
    name="Invoice, Quote & Receipt Generator",
    category=Category.BUSINESS,
    summary=(
        "Create a professional invoice, quote, or receipt as a PDF. Free documents include a "
        "small RenderCart footer; Pro documents are unbranded."
    ),
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    inputs=FileInput(accept=[], min_files=0),
    limits={
        Level.GUEST: Limit(count_per_day=2),
        Level.FREE: Limit(count_per_day=5),
        Level.DAY_PASS: Limit(fair_use_per_hour=20),
        Level.PRO: Limit(fair_use_per_hour=20),
        Level.ADMIN: Limit(fair_use_per_hour=20),
        Level.SUPER_ADMIN: Limit(fair_use_per_hour=20),
    },
    credit_cost=None,
    timeout_s=300,
    seo=SeoMeta(
        title="Free Invoice, Quote & Receipt Generator | RenderCart",
        description="Create a printable PDF invoice, quote, or receipt with multi-currency totals.",
        keywords=["invoice generator", "quote generator", "receipt maker", "free invoice PDF"],
    ),
    options=Options,
    runner=run,
)
