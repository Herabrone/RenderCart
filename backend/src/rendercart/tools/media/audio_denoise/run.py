from pathlib import Path

from pydantic import BaseModel, Field

from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import probe_media, transcode


class Options(BaseModel):
    noise_reduction_db: int = Field(
        default=20,
        ge=5,
        le=40,
        description=(
            "Noise reduction strength in decibels. Higher values can affect speech quality."
        ),
    )
    output_format: str = Field(default="mp3", pattern="^(mp3|wav)$")
    bill_credits: bool = Field(default=False, json_schema_extra={"internal": True})


def run(
    input_paths: list[Path],
    output_dir: Path,
    noise_reduction_db: int = 20,
    output_format: str = "mp3",
) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_audio_file_required")
    if not 5 <= noise_reduction_db <= 40:
        raise ValueError("noise_reduction_out_of_range")
    if output_format not in {"mp3", "wav"}:
        raise ValueError("unsupported_audio_output_format")
    media = probe_media(input_paths[0])
    if media.streams != {"audio"}:
        raise ValueError("audio_only_file_required")

    if output_format == "mp3":
        codec_args = ["-c:a", "libmp3lame", "-q:a", "3", "-f", "mp3"]
        content_type = "audio/mpeg"
    else:
        codec_args = ["-c:a", "pcm_s16le", "-f", "wav"]
        content_type = "audio/wav"
    output = transcode(
        input_paths[0],
        output_dir,
        f"noise-reduced.{output_format}",
        [
            "-i",
            str(input_paths[0]),
            "-map",
            "0:a:0",
            "-vn",
            "-af",
            f"afftdn=nr={noise_reduction_db}:nf=-25:tn=1",
            *codec_args,
        ],
        timeout_s=min(32_400, max(900, int(media.duration * 3))),
    )
    return ToolOutput(output, output.name, content_type)
