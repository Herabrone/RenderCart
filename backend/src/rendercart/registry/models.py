from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from math import ceil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from rendercart.core.access import Level


class Category(StrEnum):
    PDF = "pdf"
    IMAGE = "image"
    AUDIO_VIDEO = "audio-video"
    WRITING = "writing"
    BUSINESS = "business"
    DEVELOPER = "developer"
    VAULT = "vault"


class Runtime(StrEnum):
    CLIENT = "client"
    CPU = "cpu"
    GPU = "gpu"
    LLM = "llm"


class Queue(StrEnum):
    CPU_DEFAULT = "cpu.default"
    CPU_HEAVY = "cpu.heavy"
    CPU_SANDBOX = "cpu.sandbox"
    GPU_IMAGE = "gpu.image"
    GPU_IMAGE_PRIORITY = "gpu.image.priority"
    GPU_AUDIO = "gpu.audio"
    GPU_AUDIO_PRIORITY = "gpu.audio.priority"
    GPU_EMBED = "gpu.embed"


class JobTier(StrEnum):
    SMALL = "S"
    MEDIUM = "M"
    LARGE = "L"


@dataclass(frozen=True)
class ToolOutput:
    path: Path
    filename: str
    content_type: str
    locked_path: Path | None = None
    locked_filename: str | None = None
    locked_content_type: str | None = None
    audit_event: dict[str, object] | None = None
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class ToolPreparation:
    input_paths: list[Path]
    word_count: int = 0
    page_count: int = 0


class Limit(BaseModel):
    count_per_day: int | None = Field(default=None, ge=1)
    count_per_month: int | None = Field(default=None, ge=1)
    fair_use_per_hour: int | None = Field(default=None, ge=1)
    max_files: int | None = Field(default=None, ge=1)
    max_total_mb: int | None = Field(default=None, ge=1)
    max_pages: int | None = Field(default=None, ge=1)
    max_minutes_per_month: int | None = Field(default=None, ge=1)
    max_characters_per_job: int | None = Field(default=None, ge=1)
    max_words_per_job: int | None = Field(default=None, ge=1)
    word_count_per_day: int | None = Field(default=None, ge=1)


class FileInput(BaseModel):
    accept: list[str]
    min_files: int = Field(default=1, ge=0)
    max_files: dict[Level, int] = Field(default_factory=dict)
    max_total_mb: dict[Level, int] = Field(default_factory=dict)


class SeoMeta(BaseModel):
    title: str
    description: str
    faq: list[tuple[str, str]] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ToolManifest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str
    category: Category
    summary: str
    min_level: Level = Level.GUEST
    restricted: bool = False
    hidden: bool = False
    batchable: bool = False
    batch_max_files: int = Field(default=20, ge=2, le=50)
    runtime: Runtime
    queue: Queue | None = None
    ui: str = "generic"
    inputs: FileInput | None = None
    limits: dict[Level, Limit] = Field(default_factory=dict)
    credit_cost: int | None = Field(default=None, ge=0)
    credit_cost_per_10_pages: int = Field(default=0, ge=0)
    credit_cost_per_page: int = Field(default=0, ge=0)
    credit_cost_per_100_mb: int = Field(default=0, ge=0)
    credit_cost_per_minute: int = Field(default=0, ge=0)
    credit_cost_per_10_minutes: int = Field(default=0, ge=0)
    credit_cost_per_10000_words: int = Field(default=0, ge=0)
    credit_cost_per_1000_words: int = Field(default=0, ge=0)
    credit_cost_per_1000_chars: int = Field(default=0, ge=0)
    single_job_price_cents: int | None = Field(default=None, ge=1)
    job_tier: JobTier | None = None
    preview_then_pay: bool = False
    timeout_s: int = Field(default=300, ge=1)
    seo: SeoMeta
    options: type[BaseModel] | None = None
    runner: Any = None
    prepare: Callable[[list[Path], Path, dict[str, object]], ToolPreparation] | None = None

    @field_validator("name", "summary")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @model_validator(mode="after")
    def validate_security_and_runtime(self) -> "ToolManifest":
        if self.restricted and (self.min_level != Level.SUPER_ADMIN or not self.hidden):
            raise ValueError("restricted tools must be hidden and require super_admin")
        if self.runtime == Runtime.GPU and self.queue not in {
            Queue.GPU_IMAGE,
            Queue.GPU_IMAGE_PRIORITY,
            Queue.GPU_AUDIO,
            Queue.GPU_AUDIO_PRIORITY,
            Queue.GPU_EMBED,
        }:
            raise ValueError("GPU tools must use a GPU queue")
        if self.runtime in {Runtime.GPU, Runtime.LLM} and self.credit_cost is None:
            raise ValueError("GPU and LLM tools must declare credit_cost")
        if self.runtime == Runtime.CLIENT and self.runner is None:
            raise ValueError("client tools must declare a runner")
        if self.batchable and self.category != Category.PDF:
            raise ValueError("batch mode is currently limited to PDF tools")
        if self.batchable and self.preview_then_pay:
            raise ValueError("preview-then-pay tools cannot use batch mode")
        return self

    def public_dict(self) -> dict[str, Any]:
        """Return safe directory metadata; schema/runner internals stay private."""
        return {
            "slug": self.slug,
            "name": self.name,
            "category": self.category.value,
            "summary": self.summary,
            "min_level": self.min_level.name.lower(),
            "runtime": self.runtime.value,
            "batchable": self.batchable,
            "batch_max_files": self.batch_max_files if self.batchable else None,
            "ui": self.ui,
            "credit_cost": self.credit_cost,
            "credit_cost_per_10_pages": self.credit_cost_per_10_pages,
            "credit_cost_per_page": self.credit_cost_per_page,
            "credit_cost_per_100_mb": self.credit_cost_per_100_mb,
            "credit_cost_per_minute": self.credit_cost_per_minute,
            "credit_cost_per_10_minutes": self.credit_cost_per_10_minutes,
            "credit_cost_per_10000_words": self.credit_cost_per_10000_words,
            "credit_cost_per_1000_words": self.credit_cost_per_1000_words,
            "credit_cost_per_1000_chars": self.credit_cost_per_1000_chars,
            "single_job_price_cents": self.single_job_price_cents,
            "job_tier": self.job_tier.value if self.job_tier else None,
            "limits": {
                level.name.lower(): limit.model_dump() for level, limit in self.limits.items()
            },
            "seo": self.seo.model_dump(),
        }

    def credits_for_pages(self, page_count: int) -> int:
        """Return the manifest's base plus per-ten-page credit cost."""
        if page_count < 0:
            raise ValueError("page_count cannot be negative")
        page_units = (page_count + 9) // 10
        return (self.credit_cost or 0) + page_units * self.credit_cost_per_10_pages

    def credits_for_bytes(self, input_bytes: int) -> int:
        """Return the byte-based compute charge using decimal 100 MB units."""
        if input_bytes < 0:
            raise ValueError("input_bytes cannot be negative")
        unit_bytes = 100_000_000
        units = (input_bytes + unit_bytes - 1) // unit_bytes
        return units * self.credit_cost_per_100_mb

    def credits_for_duration_seconds(self, duration_seconds: float) -> int:
        """Return the per-minute credit cost, rounding any partial minute up."""
        if duration_seconds < 0:
            raise ValueError("duration_seconds cannot be negative")
        if duration_seconds == 0 or self.credit_cost_per_minute == 0:
            return 0
        return ceil(duration_seconds / 60) * self.credit_cost_per_minute

    def credits_for_ten_minute_bands(self, duration_seconds: float) -> int:
        """Charge per started ten-minute band for long-form audio processing."""
        if duration_seconds < 0:
            raise ValueError("duration_seconds cannot be negative")
        if duration_seconds == 0 or self.credit_cost_per_10_minutes == 0:
            return 0
        return ceil(duration_seconds / 600) * self.credit_cost_per_10_minutes

    def credits_for_word_bands(self, word_count: int) -> int:
        """Charge per started 10,000-word band for LLM document processing."""
        if word_count < 0:
            raise ValueError("word_count cannot be negative")
        if word_count == 0 or self.credit_cost_per_10000_words == 0:
            return 0
        return ceil(word_count / 10_000) * self.credit_cost_per_10000_words

    def credits_for_1000_word_bands(self, word_count: int) -> int:
        """Return per-started-1,000-word pricing."""
        if word_count < 0:
            raise ValueError("word_count cannot be negative")
        if word_count == 0 or self.credit_cost_per_1000_words == 0:
            return 0
        return ceil(word_count / 1_000) * self.credit_cost_per_1000_words

    def credits_for_text_characters(self, character_count: int) -> int:
        """Return the per-thousand-character charge, rounding partial units up."""
        if character_count < 0:
            raise ValueError("character_count cannot be negative")
        if character_count == 0 or self.credit_cost_per_1000_chars == 0:
            return 0
        units = ceil(character_count / 1000)
        return units * self.credit_cost_per_1000_chars

    def detail_dict(self) -> dict[str, Any]:
        options_schema = self.options.model_json_schema() if self.options else None
        if options_schema and self.options:
            hidden_fields = {
                name
                for name, field in self.options.model_fields.items()
                if isinstance(field.json_schema_extra, dict)
                and field.json_schema_extra.get("internal")
            }
            properties = options_schema.get("properties", {})
            for name in hidden_fields:
                properties.pop(name, None)
            if "required" in options_schema:
                options_schema["required"] = [
                    name for name in options_schema["required"] if name not in hidden_fields
                ]
        return {
            **self.public_dict(),
            "inputs": (
                {
                    "accept": self.inputs.accept,
                    "min_files": self.inputs.min_files,
                    "max_files": {
                        level.name.lower(): count for level, count in self.inputs.max_files.items()
                    },
                    "max_total_mb": {
                        level.name.lower(): size for level, size in self.inputs.max_total_mb.items()
                    },
                }
                if self.inputs
                else None
            ),
            "options_schema": options_schema,
        }
