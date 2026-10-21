from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from pydantic import BaseModel, Field

from rendercart.core.config import get_settings
from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import probe_media

_DIARIZATION_ATTRIBUTION = (
    "Speaker diarization uses pyannote/speaker-diarization-community-1 by pyannote, "
    "revision 3533c8cf8e369892e6b79ff1bf80f7b0286a54ee. Licensed under CC BY 4.0: "
    "https://creativecommons.org/licenses/by/4.0/. Model source: "
    "https://huggingface.co/pyannote/speaker-diarization-community-1."
)


class Options(BaseModel):
    language: str | None = Field(
        default=None,
        max_length=3,
        pattern=r"^(?:[a-zA-Z]{2,3})?$",
        description=(
            "Optional language code, such as en or fr. Leave blank for automatic detection."
        ),
    )
    include_speakers: bool = Field(
        default=False,
        description=(
            "Identify speaker turns. Requires the configured Hugging Face token to have "
            "access to the pyannote Community-1 model."
        ),
    )
    bill_credits: bool = Field(default=False, json_schema_extra={"internal": True})
    max_minutes_per_month: int | None = Field(
        default=None, json_schema_extra={"internal": True}
    )


def _load_model() -> Any:
    try:
        import ctranslate2
        from faster_whisper import WhisperModel
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise ValueError("transcription_runtime_unavailable") from exc
    if ctranslate2.get_cuda_device_count() < 1:
        raise ValueError("gpu_unavailable")
    settings = get_settings()
    try:
        model_path = snapshot_download(
            repo_id=settings.transcription_model_id,
            revision=settings.transcription_model_revision,
        )
        return WhisperModel(model_path, device="cuda", compute_type="float16")
    except Exception as exc:
        raise ValueError("transcription_model_unavailable") from exc


@lru_cache(maxsize=1)
def _cached_model(model_id: str, revision: str) -> Any:
    del model_id, revision
    return _load_model()


@lru_cache(maxsize=1)
def _cached_diarization_pipeline() -> Any:
    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise ValueError("diarization_runtime_unavailable") from exc
    settings = get_settings()
    if settings.diarization_hf_token is None:
        raise ValueError("diarization_access_required")
    try:
        pipeline = Pipeline.from_pretrained(
            settings.diarization_model_id,
            revision=settings.diarization_model_revision,
            token=settings.diarization_hf_token.get_secret_value(),
        )
        if pipeline is None:
            raise ValueError("diarization_model_unavailable")
        pipeline.to(torch.device("cuda"))
        return pipeline
    except ValueError:
        raise
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in {401, 403} or type(exc).__name__ == "GatedRepoError":
            raise ValueError("diarization_access_required") from exc
        raise ValueError("diarization_model_unavailable") from exc


def _speaker_turns(pipeline: Any, media_path: Path) -> list[dict[str, Any]]:
    result = pipeline(str(media_path))
    annotation = getattr(result, "exclusive_speaker_diarization", None)
    if annotation is None:
        annotation = getattr(result, "speaker_diarization", result)
    return [
        {
            "start": max(0.0, float(turn.start)),
            "end": max(float(turn.start), float(turn.end)),
            "speaker": str(speaker),
        }
        for turn, _track, speaker in annotation.itertracks(yield_label=True)
    ]


def _speaker_for_interval(
    start: float, end: float, turns: list[dict[str, Any]]
) -> str | None:
    best_speaker: str | None = None
    best_overlap = 0.0
    for turn in turns:
        overlap = min(end, float(turn["end"])) - max(start, float(turn["start"]))
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = str(turn["speaker"])
    return best_speaker


def _timestamp(seconds: float, *, srt: bool = False) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}{separator}{millis:03d}"


def run(
    input_paths: list[Path],
    output_dir: Path,
    language: str | None = None,
    include_speakers: bool = False,
    bill_credits: bool = False,
    max_minutes_per_month: int | None = None,
    progress: Callable[[int], None] | None = None,
) -> ToolOutput:
    del bill_credits, max_minutes_per_month
    if len(input_paths) != 1:
        raise ValueError("exactly_one_media_file_required")
    media = probe_media(input_paths[0])
    if "audio" not in media.streams:
        raise ValueError("audio_stream_required")
    settings = get_settings()
    model = _cached_model(settings.transcription_model_id, settings.transcription_model_revision)
    segments, info = model.transcribe(
        str(input_paths[0]),
        language=language or None,
        beam_size=5,
        vad_filter=True,
    )
    rows: list[dict[str, Any]] = []
    transcript_lines: list[str] = []
    srt_lines: list[str] = []
    total_duration = max(media.duration, float(getattr(info, "duration", 0) or 0), 0.001)
    for segment in segments:
        text = str(segment.text).strip()
        if not text:
            continue
        start = max(0.0, float(segment.start))
        end = max(start, float(segment.end))
        rows.append({"start": start, "end": end, "text": text})
        if progress:
            ceiling = 85 if include_speakers else 99
            progress(min(ceiling, max(1, round(end / total_duration * ceiling))))
    if not rows:
        raise ValueError("transcription_empty")

    speaker_turns: list[dict[str, Any]] = []
    if include_speakers:
        if progress:
            progress(87)
        speaker_turns = _speaker_turns(_cached_diarization_pipeline(), input_paths[0])
        for row in rows:
            row["speaker"] = _speaker_for_interval(
                float(row["start"]), float(row["end"]), speaker_turns
            )
        if progress:
            progress(95)

    for index, row in enumerate(rows, start=1):
        text = str(row["text"])
        speaker = row.get("speaker")
        line = f"{speaker}: {text}" if speaker else text
        transcript_lines.append(line)
        srt_lines.extend(
            [
                str(index),
                f"{_timestamp(float(row['start']), srt=True)} --> "
                f"{_timestamp(float(row['end']), srt=True)}",
                line,
                "",
            ]
        )

    metadata = {
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration_seconds": total_duration,
        "segments": rows,
    }
    if include_speakers:
        metadata["speaker_turns"] = speaker_turns
    output = output_dir / "transcription.zip"
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("transcript.txt", "\n".join(transcript_lines) + "\n")
        archive.writestr("transcription.srt", "\n".join(srt_lines))
        archive.writestr("transcript.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        if include_speakers:
            archive.writestr("speaker-attribution.txt", _DIARIZATION_ATTRIBUTION)
            archive.writestr(
                "speakers.json",
                json.dumps(speaker_turns, ensure_ascii=False, indent=2),
            )
    if progress:
        progress(100)
    return ToolOutput(output, output.name, "application/zip")
