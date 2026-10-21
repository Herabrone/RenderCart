from pydantic import BaseModel, EmailStr, Field, field_validator

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
from rendercart.tools.pdf.esign.run import run


class ESignOptions(BaseModel):
    signer_name: str = Field(
        min_length=1,
        max_length=120,
        json_schema_extra={"internal": True, "sensitive": True},
    )
    signer_email: EmailStr = Field(json_schema_extra={"internal": True, "sensitive": True})
    page_number: int = Field(ge=1, json_schema_extra={"internal": True})
    consented: bool = Field(default=False, json_schema_extra={"internal": True})
    signer_ip: str = Field(
        default="unknown",
        max_length=64,
        json_schema_extra={"internal": True, "sensitive": True},
    )
    signed_at: str = Field(default="", json_schema_extra={"internal": True})

    @field_validator("signer_name")
    @classmethod
    def signer_name_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("signer_name_required")
        return value.strip()


TOOL = ToolManifest(
    slug="esign-pdf",
    name="Sign PDF",
    category=Category.PDF,
    summary="Add a visual signature to a PDF and keep a timestamped audit record.",
    ui="custom",
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    inputs=FileInput(
        accept=["application/pdf"],
        min_files=2,
        max_files={Level.GUEST: 2, Level.FREE: 2, Level.PRO: 2},
        max_total_mb={Level.GUEST: 10, Level.FREE: 10, Level.PRO: 500},
    ),
    limits={
        Level.GUEST: Limit(count_per_month=1, max_files=2, max_total_mb=10),
        Level.FREE: Limit(count_per_month=1, max_files=2, max_total_mb=10),
        Level.PRO: Limit(fair_use_per_hour=30, max_files=2, max_total_mb=500),
    },
    credit_cost=0,
    single_job_price_cents=199,
    job_tier=JobTier.MEDIUM,
    timeout_s=300,
    seo=SeoMeta(
        title="Sign PDF Online | RenderCart",
        description="Add a visual electronic signature and retain a PDF signing audit record.",
        keywords=["sign pdf", "electronic signature pdf", "e-sign pdf"],
        faq=[
            (
                "Is this a cryptographic digital signature?",
                "No. This adds a visual signature mark and an audit record; it does not verify "
                "identity or create a certificate-backed digital signature.",
            ),
            (
                "What is recorded?",
                "The audit record includes the signer name and email, request IP, signing time, "
                "selected page, and SHA-256 hashes of the source and signed PDF.",
            ),
        ],
    ),
    options=ESignOptions,
    runner=run,
)
