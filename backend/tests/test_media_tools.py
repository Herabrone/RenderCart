from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from rendercart.jobs.tasks import _verify_file
from rendercart.tools.media.audio_convert.run import run as convert_audio
from rendercart.tools.media.audio_extract.run import run as extract_audio
from rendercart.tools.media.audio_trim.run import Options as AudioTrimOptions
from rendercart.tools.media.audio_trim.run import run as trim_audio
from rendercart.tools.media.common import probe_media
from rendercart.tools.media.video_compress.run import run as compress_video
from rendercart.tools.media.video_convert.run import run as convert_video
from rendercart.tools.media.video_gif.run import run as make_gif
from rendercart.tools.media.video_merge.run import run as merge_videos
from rendercart.tools.media.video_trim.run import run as trim_video


def _require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe are needed for media integration tests")


def _make_wav(path: Path, seconds: float = 2) -> None:
    sample_rate = 16_000
    frames = int(sample_rate * seconds)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * frames)


def _make_video(path: Path) -> None:
    _require_ffmpeg()
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=64x64:r=10:d=2",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=2",
            "-shortest",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


def test_audio_conversion_and_trim_produce_decodable_outputs(tmp_path: Path) -> None:
    _require_ffmpeg()
    source = tmp_path / "tone.wav"
    _make_wav(source)

    converted = convert_audio([source], tmp_path, "flac")
    trimmed = trim_audio([source], tmp_path, 0.25, 0.9)

    assert converted.content_type == "audio/flac"
    assert probe_media(converted.path).streams == frozenset({"audio"})
    assert trimmed.content_type == "audio/mpeg"
    duration = probe_media(trimmed.path).duration
    assert 0.5 <= duration <= 0.8


def test_audio_trim_rejects_end_after_media_duration(tmp_path: Path) -> None:
    _require_ffmpeg()
    source = tmp_path / "tone.wav"
    _make_wav(source, seconds=1)

    with pytest.raises(ValueError, match="trim_end_exceeds_duration"):
        trim_audio([source], tmp_path, 0.25, 1.5)
    with pytest.raises(ValueError, match="end_must_follow_start"):
        AudioTrimOptions(start_seconds=1, end_seconds=1)


def test_video_convert_compress_trim_and_audio_extract(tmp_path: Path) -> None:
    source = tmp_path / "sample.mp4"
    _make_video(source)
    _verify_file(source, "video/mp4")

    converted = convert_video([source], tmp_path, "webm")
    compressed = compress_video([source], tmp_path, quality=28)
    trimmed = trim_video([source], tmp_path, 0.25, 1.1)
    audio = extract_audio([source], tmp_path)

    assert converted.content_type == "video/webm"
    assert "video" in probe_media(converted.path).streams
    assert compressed.content_type == "video/mp4"
    assert "video" in probe_media(compressed.path).streams
    assert 0.7 <= probe_media(trimmed.path).duration <= 1.1
    assert probe_media(audio.path).streams == frozenset({"audio"})


def test_video_to_gif_exports_an_animated_clip(tmp_path: Path) -> None:
    from PIL import Image

    source = tmp_path / "sample.mp4"
    _make_video(source)

    result = make_gif([source], tmp_path, start_seconds=0.25, duration_seconds=0.75)

    assert result.content_type == "image/gif"
    with Image.open(result.path) as gif:
        assert gif.format == "GIF"
        assert gif.n_frames > 1


def test_video_merger_joins_clips_in_order(tmp_path: Path) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    _make_video(first)
    _make_video(second)

    result = merge_videos([first, second], tmp_path)

    assert result.content_type == "video/mp4"
    merged = probe_media(result.path)
    assert merged.streams == frozenset({"audio", "video"})
    assert 3.5 <= merged.duration <= 4.3


def test_media_upload_validation_rejects_playlist_and_mismatched_mime(tmp_path: Path) -> None:
    playlist = tmp_path / "playlist.m3u8"
    playlist.write_text("#EXTM3U\nhttps://example.invalid/stream", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid_media_file"):
        _verify_file(playlist, "video/mp4")

    audio = tmp_path / "tone.wav"
    _make_wav(audio)
    with pytest.raises(ValueError, match="media_type_mismatch"):
        _verify_file(audio, "video/mp4")
