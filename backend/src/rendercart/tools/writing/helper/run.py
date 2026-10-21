from collections.abc import Callable
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from rendercart.registry.models import ToolOutput, ToolPreparation
from rendercart.tools.writing.common import prepare_helper, run_helper


class Options(BaseModel):
    helper_type: Literal[
        "email", "title", "caption", "product-description", "social-post", "agenda"
    ] = Field(
        default="email",
        title="Writing template",
    )
    prompt: str = Field(
        min_length=5,
        max_length=4_000,
        title="What should it write?",
        description="Add the details, key points, and any length or format requirements.",
        json_schema_extra={"widget": "textarea", "sensitive": True},
    )
    audience: str = Field(
        default="",
        max_length=160,
        title="Audience (optional)",
        json_schema_extra={"sensitive": True},
    )


def prepare(input_paths: list[Path], workdir: Path, options: dict[str, object]) -> ToolPreparation:
    return prepare_helper(input_paths, workdir, options)


def run(
    input_paths: list[Path],
    output_dir: Path,
    job_id: UUID | None = None,
    progress: Callable[[int], None] | None = None,
) -> ToolOutput:
    return run_helper(input_paths, output_dir, job_id=job_id, progress=progress)
