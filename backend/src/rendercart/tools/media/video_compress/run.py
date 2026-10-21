from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import probe_media, transcode


class Options(BaseModel):
    quality: Literal[18, 23, 28] = Field(
        default=23, description="CRF quality: 18 high, 23 balanced, 28 smaller"
    )
    bill_credits: bool = Field(default=False, json_schema_extra={"internal": True})


def run(
    input_paths: list[Path],
    output_dir: Path,
    quality: int = 23,
    bill_credits: bool = False,
) -> ToolOutput:
    del bill_credits
    if len(input_paths) != 1:
        raise ValueError("exactly_one_video_file_required")
    if quality not in {18, 23, 28}:
        raise ValueError("unsupported_compression_quality")
    if "video" not in probe_media(input_paths[0]).streams:
        raise ValueError("video_stream_required")
    output = transcode(
        input_paths[0],
        output_dir,
        "compressed.mp4",
        [
            "-i",
            str(input_paths[0]),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(quality),
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
        ],
        timeout_s=1800,
    )
    return ToolOutput(output, output.name, "video/mp4")
