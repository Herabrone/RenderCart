from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import probe_media, transcode


class Options(BaseModel):
    start_seconds: float = Field(default=0, ge=0)
    end_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def end_after_start(self) -> "Options":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_must_follow_start")
        return self


def run(
    input_paths: list[Path], output_dir: Path, start_seconds: float, end_seconds: float
) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_video_file_required")
    info = probe_media(input_paths[0])
    if "video" not in info.streams:
        raise ValueError("video_stream_required")
    if end_seconds > info.duration:
        raise ValueError("trim_end_exceeds_duration")
    output = transcode(
        input_paths[0],
        output_dir,
        "trimmed.mp4",
        [
            "-ss",
            f"{start_seconds:.3f}",
            "-i",
            str(input_paths[0]),
            "-t",
            f"{end_seconds - start_seconds:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-f",
            "mp4",
        ],
        timeout_s=1800,
    )
    return ToolOutput(output, output.name, "video/mp4")
