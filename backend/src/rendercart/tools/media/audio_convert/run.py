from pathlib import Path

from pydantic import BaseModel, Field

from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import probe_media, transcode


class Options(BaseModel):
    output_format: str = Field(default="mp3", pattern="^(mp3|wav|flac|m4a|ogg)$")


_ENCODERS: dict[str, tuple[list[str], str]] = {
    "mp3": (["-c:a", "libmp3lame", "-q:a", "3", "-f", "mp3"], "audio/mpeg"),
    "wav": (["-c:a", "pcm_s16le", "-f", "wav"], "audio/wav"),
    "flac": (["-c:a", "flac", "-f", "flac"], "audio/flac"),
    "m4a": (["-c:a", "aac", "-b:a", "192k", "-f", "ipod"], "audio/mp4"),
    "ogg": (["-c:a", "libvorbis", "-q:a", "5", "-f", "ogg"], "audio/ogg"),
}


def run(input_paths: list[Path], output_dir: Path, output_format: str = "mp3") -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_audio_file_required")
    if output_format not in _ENCODERS:
        raise ValueError("unsupported_audio_output_format")
    if "audio" not in probe_media(input_paths[0]).streams:
        raise ValueError("audio_stream_required")
    codec_args, content_type = _ENCODERS[output_format]
    output = transcode(
        input_paths[0],
        output_dir,
        f"converted.{output_format}",
        ["-i", str(input_paths[0]), "-map", "0:a:0", "-vn", *codec_args],
    )
    return ToolOutput(output, output.name, content_type)
