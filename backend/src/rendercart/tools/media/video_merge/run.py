from pathlib import Path

from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import probe_media, transcode


def run(input_paths: list[Path], output_dir: Path) -> ToolOutput:
    if not 2 <= len(input_paths) <= 10:
        raise ValueError("video_merge_file_count_out_of_range")
    for path in input_paths:
        streams = probe_media(path).streams
        if "video" not in streams or "audio" not in streams:
            raise ValueError("each_video_needs_audio_and_video_streams")

    filters: list[str] = []
    for index in range(len(input_paths)):
        filters.append(
            f"[{index}:v:0]scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,"
            f"setpts=PTS-STARTPTS[v{index}]"
        )
        filters.append(
            f"[{index}:a:0]aresample=48000:async=1:first_pts=0,asetpts=PTS-STARTPTS[a{index}]"
        )
    inputs = "".join(f"[v{index}][a{index}]" for index in range(len(input_paths)))
    filters.append(f"{inputs}concat=n={len(input_paths)}:v=1:a=1[outv][outa]")
    args = [item for path in input_paths for item in ("-i", str(path))]
    args.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-map",
            "[outa]",
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
        ]
    )
    output = transcode(input_paths[0], output_dir, "merged.mp4", args, timeout_s=3600)
    return ToolOutput(output, output.name, "video/mp4")
