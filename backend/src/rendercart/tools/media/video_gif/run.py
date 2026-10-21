from pathlib import Path

from pydantic import BaseModel, Field

from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import probe_media, transcode


class Options(BaseModel):
    start_seconds: float = Field(default=0, ge=0)
    duration_seconds: float = Field(default=5, gt=0, le=30)


def run(
    input_paths: list[Path],
    output_dir: Path,
    start_seconds: float = 0,
    duration_seconds: float = 5,
) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_video_file_required")
    if not 0 < duration_seconds <= 30:
        raise ValueError("gif_duration_out_of_range")
    info = probe_media(input_paths[0])
    if "video" not in info.streams:
        raise ValueError("video_stream_required")
    if start_seconds < 0 or start_seconds + duration_seconds > info.duration:
        raise ValueError("gif_range_exceeds_duration")
    output = transcode(
        input_paths[0],
        output_dir,
        "animation.gif",
        [
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            str(input_paths[0]),
            "-t",
            f"{duration_seconds:.3f}",
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            "fps=12,scale=480:-1:flags=lanczos",
            "-loop",
            "0",
            "-f",
            "gif",
        ],
        timeout_s=900,
    )
    return ToolOutput(output, output.name, "image/gif")
