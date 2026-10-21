from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypedDict

from rendercart.core.config import get_settings
from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import probe_media, transcode
from rendercart.tools.media.transcription.run import _cached_model, _timestamp


class SubtitleSegment(TypedDict):
    start: float
    end: float
    text: str


def _escape_filter_path(path: Path) -> str:
    """Escape a generated worker path for FFmpeg's subtitles filter syntax."""
    return (
        path.resolve()
        .as_posix()
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def _format_subtitles(rows: list[SubtitleSegment], output: Literal["srt", "vtt"]) -> str:
    blocks: list[str] = []
    if output == "vtt":
        blocks.append("WEBVTT\n")
    for index, row in enumerate(rows, start=1):
        start = float(row["start"])
        end = float(row["end"])
        text = str(row["text"])
        if output == "srt":
            start_stamp = _timestamp(start, srt=True)
            end_stamp = _timestamp(end, srt=True)
            blocks.append(f"{index}\n{start_stamp} --> {end_stamp}\n{text}\n")
        else:
            blocks.append(f"{index}\n{_timestamp(start)} --> {_timestamp(end)}\n{text}\n")
    return "\n".join(blocks)


def run(
    input_paths: list[Path],
    output_dir: Path,
    language: str | None = None,
    output: Literal["srt", "vtt", "burn_in"] = "srt",
    font_size: int = 28,
    font_color: Literal["white", "yellow", "cyan"] = "white",
    bill_credits: bool = False,
    max_minutes_per_month: int | None = None,
    progress: Callable[[int], None] | None = None,
) -> ToolOutput:
    del bill_credits, max_minutes_per_month
    if len(input_paths) != 1:
        raise ValueError("exactly_one_media_file_required")
    if output not in {"srt", "vtt", "burn_in"}:
        raise ValueError("unsupported_subtitle_output")
    if not 18 <= font_size <= 48:
        raise ValueError("subtitle_font_size_out_of_range")
    media_path = input_paths[0]
    media = probe_media(media_path)
    if "audio" not in media.streams:
        raise ValueError("audio_stream_required")
    if output == "burn_in" and "video" not in media.streams:
        raise ValueError("video_stream_required_for_burn_in")

    settings = get_settings()
    model = _cached_model(settings.transcription_model_id, settings.transcription_model_revision)
    segments, _info = model.transcribe(
        str(media_path), language=language or None, beam_size=5, vad_filter=True
    )
    rows: list[SubtitleSegment] = []
    total_duration = max(media.duration, 0.001)
    for segment in segments:
        text = str(segment.text).strip()
        if not text:
            continue
        start = max(0.0, float(segment.start))
        end = max(start, float(segment.end))
        rows.append({"start": start, "end": end, "text": text})
        if progress:
            progress(min(80, max(1, round(end / total_duration * 80))))
    if not rows:
        raise ValueError("transcription_empty")

    if output != "burn_in":
        extension = output
        output_path = output_dir / f"subtitles.{extension}"
        output_path.write_text(_format_subtitles(rows, output), encoding="utf-8")
        if progress:
            progress(100)
        return ToolOutput(
            output_path,
            output_path.name,
            "application/x-subrip" if output == "srt" else "text/vtt",
        )

    subtitle_path = output_dir / "captions.srt"
    subtitle_path.write_text(_format_subtitles(rows, "srt"), encoding="utf-8")
    if progress:
        progress(85)
    primary_color = {
        "white": "&H00FFFFFF",
        "yellow": "&H0000FFFF",
        "cyan": "&H00FFFF00",
    }[font_color]
    force_style = (
        f"FontSize={font_size},PrimaryColour={primary_color},Outline=2,Shadow=1,Alignment=2"
    )
    output_path = transcode(
        media_path,
        output_dir,
        "subtitled.mp4",
        [
            "-i",
            str(media_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            f"subtitles='{_escape_filter_path(subtitle_path)}':force_style='{force_style}'",
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
    subtitle_path.unlink(missing_ok=True)
    if progress:
        progress(100)
    return ToolOutput(output_path, output_path.name, "video/mp4")
