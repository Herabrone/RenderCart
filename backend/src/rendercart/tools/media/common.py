from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

AUDIO_MIMES = [
    "audio/aac",
    "audio/flac",
    "audio/m4a",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/opus",
    "audio/wav",
    "audio/webm",
    "audio/x-flac",
    "audio/x-m4a",
    "audio/x-wav",
]
VIDEO_MIMES = [
    "video/3gpp",
    "video/mp2t",
    "video/mp4",
    "video/mpeg",
    "video/ogg",
    "video/quicktime",
    "video/webm",
    "video/x-matroska",
    "video/x-msvideo",
]
SUBTITLE_MIMES = ["application/x-subrip", "text/vtt"]
_SUBTITLE_TIMECODE = re.compile(
    r"(?P<start>(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3})\s+-->\s+"
    r"(?P<end>(?:\d{2}:)?\d{2}:\d{2}[.,]\d{3})(?:\s+.*)?$"
)


@dataclass(frozen=True)
class MediaInfo:
    streams: frozenset[str]
    duration: float


def subtitle_duration_seconds(path: Path, content_type: str) -> float:
    """Validate a bounded SRT/VTT upload and return its final cue end time."""
    if content_type not in SUBTITLE_MIMES:
        raise ValueError("unsupported_subtitle_format")
    content = path.read_bytes()
    if not content or len(content) > 10_485_760 or b"\x00" in content:
        raise ValueError("invalid_subtitle_file")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid_subtitle_file") from exc
    if content_type == "text/vtt" and not text.lstrip().startswith("WEBVTT"):
        raise ValueError("invalid_subtitle_file")
    if content_type == "application/x-subrip" and text.lstrip().startswith("WEBVTT"):
        raise ValueError("subtitle_type_mismatch")

    def to_seconds(value: str) -> float:
        parts = value.replace(",", ".").split(":")
        if len(parts) == 2:
            hours = "0"
            minutes, seconds_millis = parts
        elif len(parts) == 3:
            hours, minutes, seconds_millis = parts
        else:
            raise ValueError("invalid_subtitle_timestamp")
        seconds, millis = seconds_millis.split(".")
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000

    timings = [
        (to_seconds(match.group("start")), to_seconds(match.group("end")))
        for line in text.splitlines()
        if (match := _SUBTITLE_TIMECODE.fullmatch(line.strip()))
    ]
    if any(end <= start for start, end in timings):
        raise ValueError("invalid_subtitle_timing")
    ends = [end for _start, end in timings]
    if not ends or len(ends) > 6000:
        raise ValueError("subtitle_cue_count_out_of_range")
    duration = max(ends)
    if duration <= 0 or duration > 10_800:
        raise ValueError("media_duration_out_of_range")
    return duration


def has_supported_media_signature(path: Path, content_type: str) -> bool:
    with path.open("rb") as source:
        header = source.read(16)
    if len(header) < 4:
        return False
    if header[:4] == b"RIFF":
        return header[8:12] in {b"WAVE", b"AVI "} and content_type in AUDIO_MIMES + VIDEO_MIMES
    if header[4:8] == b"ftyp":
        return content_type in {
            "audio/mp4",
            "audio/m4a",
            "audio/x-m4a",
            "video/mp4",
            "video/quicktime",
        }
    if header.startswith(b"\x1aE\xdf\xa3"):
        return content_type in {"audio/webm", "video/webm", "video/x-matroska"}
    if header.startswith((b"ID3", b"OggS", b"fLaC")):
        return content_type in AUDIO_MIMES + ["video/ogg"]
    if header[0] == 0xFF and header[1] & 0xE0 == 0xE0:
        return content_type in {"audio/aac", "audio/mpeg", "video/mp2t", "video/mpeg"}
    if header[0] == 0x47 and content_type == "video/mp2t":
        return True
    return False


def probe_media(path: Path) -> MediaInfo:
    if not shutil.which("ffprobe"):
        raise ValueError("ffmpeg_unavailable")
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,crypto,data",
                "-show_entries",
                "format=duration",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("media_probe_timeout") from exc
    if result.returncode:
        raise ValueError("invalid_media_file")
    try:
        payload = json.loads(result.stdout)
        streams = frozenset(
            str(stream.get("codec_type"))
            for stream in payload.get("streams", [])
            if stream.get("codec_type") in {"audio", "video"}
        )
        duration = float(payload.get("format", {}).get("duration", 0))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid_media_file") from exc
    if not streams or duration <= 0 or duration > 10_800:
        raise ValueError("media_duration_out_of_range")
    return MediaInfo(streams=streams, duration=duration)


def transcode(
    source: Path,
    output_dir: Path,
    filename: str,
    args: list[str],
    *,
    timeout_s: int = 900,
) -> Path:
    if not shutil.which("ffmpeg"):
        raise ValueError("ffmpeg_unavailable")
    output = output_dir / filename
    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-protocol_whitelist",
        "file,crypto,data",
        *args,
        str(output),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        output.unlink(missing_ok=True)
        raise ValueError("media_processing_timeout") from exc
    if result.returncode or not output.is_file() or output.stat().st_size == 0:
        output.unlink(missing_ok=True)
        raise ValueError("media_processing_failed")
    return output
