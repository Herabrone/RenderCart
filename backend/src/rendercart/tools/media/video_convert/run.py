from pathlib import Path

from pydantic import BaseModel, Field

from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import probe_media, transcode


class Options(BaseModel):
    output_format: str = Field(default="mp4", pattern="^(mp4|webm|mov)$")


_FORMATS: dict[str, tuple[list[str], str]] = {
    "mp4": (
        [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
        ],
        "video/mp4",
    ),
    "webm": (
        [
            "-c:v",
            "libvpx-vp9",
            "-deadline",
            "good",
            "-crf",
            "32",
            "-b:v",
            "0",
            "-c:a",
            "libopus",
            "-f",
            "webm",
        ],
        "video/webm",
    ),
    "mov": (
        ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-f", "mov"],
        "video/quicktime",
    ),
}


def run(input_paths: list[Path], output_dir: Path, output_format: str = "mp4") -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_video_file_required")
    if output_format not in _FORMATS:
        raise ValueError("unsupported_video_output_format")
    if "video" not in probe_media(input_paths[0]).streams:
        raise ValueError("video_stream_required")
    codec_args, content_type = _FORMATS[output_format]
    output = transcode(
        input_paths[0],
        output_dir,
        f"converted.{output_format}",
        ["-i", str(input_paths[0]), "-map", "0:v:0", "-map", "0:a:0?", *codec_args],
        timeout_s=1800,
    )
    return ToolOutput(output, output.name, content_type)
