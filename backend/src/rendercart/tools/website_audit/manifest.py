from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, Field, field_validator

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
from rendercart.safety.fetch import UnsafeUrlError, validate_public_http_url
from rendercart.tools.website_audit.run import run


class Options(BaseModel):
    url: str = Field(
        min_length=8,
        max_length=2048,
        title="Website URL",
        description="Public HTTPS page to audit; the browser's outbound connections are filtered.",
        json_schema_extra={"format": "uri", "sensitive": True},
    )
    device: str = Field(
        default="mobile",
        title="Device profile",
        json_schema_extra={"enum": ["mobile", "desktop"]},
    )

    @field_validator("url")
    @classmethod
    def validate_public_https_url(cls, value: str) -> str:
        candidate = value.strip()
        try:
            scheme, _host, port, _pinned_ip, _path = validate_public_http_url(candidate)
            parsed = urlsplit(candidate)
        except (UnsafeUrlError, ValueError) as exc:
            raise ValueError("Enter a public HTTPS website URL") from exc
        if (
            scheme != "https"
            or port != 443
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("Website audits require a public HTTPS URL on port 443")
        return urlunsplit((scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))

    @field_validator("device")
    @classmethod
    def validate_device(cls, value: str) -> str:
        if value not in {"mobile", "desktop"}:
            raise ValueError("Choose a mobile or desktop audit")
        return value


TOOL = ToolManifest(
    slug="website-audit",
    name="Website Speed & SEO Audit",
    category=Category.DEVELOPER,
    summary=(
        "Measure performance, accessibility, best practices, and SEO with Lighthouse. "
        "Reports include scores, key metrics, and prioritized recommendations."
    ),
    runtime=Runtime.CPU,
    queue=Queue.CPU_SANDBOX,
    ui="generic",
    inputs=FileInput(accept=[], min_files=0),
    limits={
        Level.GUEST: Limit(count_per_day=1),
        Level.FREE: Limit(count_per_day=1),
        Level.DAY_PASS: Limit(fair_use_per_hour=4),
        Level.PRO: Limit(fair_use_per_hour=4),
        Level.ADMIN: Limit(fair_use_per_hour=4),
        Level.SUPER_ADMIN: Limit(fair_use_per_hour=4),
    },
    credit_cost=2,
    job_tier=JobTier.SMALL,
    timeout_s=240,
    seo=SeoMeta(
        title="Free Website Speed & SEO Audit | RenderCart",
        description=(
            "Run a Lighthouse audit for website performance, accessibility, best practices, "
            "and SEO. Download a PDF report with scores and recommendations."
        ),
        keywords=["website speed test", "Lighthouse audit", "SEO audit", "accessibility audit"],
    ),
    options=Options,
    runner=run,
)
