from pathlib import Path

from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import probe_media, transcode


def run(input_paths: list[Path], output_dir: Path) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_video_file_required")
    info = probe_media(input_paths[0])
    if "video" not in info.streams or "audio" not in info.streams:
        raise ValueError("video_with_audio_stream_required")
    output = transcode(
        input_paths[0],
        output_dir,
        "extracted-audio.mp3",
        [
            "-i",
            str(input_paths[0]),
            "-map",
            "0:a:0",
            "-vn",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "3",
            "-f",
            "mp3",
        ],
    )
    return ToolOutput(output, output.name, "audio/mpeg")
