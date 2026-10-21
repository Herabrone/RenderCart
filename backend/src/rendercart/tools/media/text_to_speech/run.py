from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from rendercart.core.config import get_settings
from rendercart.registry.models import ToolOutput
from rendercart.tools.media.common import transcode

_SUPPORTED_VOICES = {
    "af_heart",
    "af_bella",
    "af_nicole",
    "af_sarah",
    "af_sky",
    "am_adam",
    "am_michael",
    "bf_emma",
    "bf_isabella",
    "bm_george",
    "bm_lewis",
}


class Options(BaseModel):
    voice: Literal[
        "af_heart",
        "af_bella",
        "af_nicole",
        "af_sarah",
        "af_sky",
        "am_adam",
        "am_michael",
        "bf_emma",
        "bf_isabella",
        "bm_george",
        "bm_lewis",
    ] = Field(default="af_heart", description="English voice for the generated speech.")
    speed: float = Field(default=1.0, ge=0.7, le=1.3, description="Speech speed from 0.7× to 1.3×.")
    output_format: Literal["wav", "mp3"] = Field(default="mp3")
    max_characters: int | None = Field(default=None, json_schema_extra={"internal": True})
    bill_credits: bool = Field(default=False, json_schema_extra={"internal": True})


@lru_cache(maxsize=1)
def _load_pipeline() -> Any:
    try:
        import torch
        from huggingface_hub import snapshot_download

        from rendercart.tools.media.text_to_speech._kokoro_vendor import KModel, KPipeline
    except ImportError as exc:
        raise ValueError("tts_runtime_unavailable") from exc
    if not torch.cuda.is_available():
        raise ValueError("gpu_unavailable")
    settings = get_settings()
    try:
        from huggingface_hub import snapshot_download

        model_dir = Path(
            snapshot_download(
                repo_id=settings.tts_model_id,
                revision=settings.tts_model_revision,
                allow_patterns=["config.json", "kokoro-v1_0.pth"],
            )
        )
        config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        model = (
            KModel(
                repo_id=settings.tts_model_id,
                config=config,
                model=str(model_dir / "kokoro-v1_0.pth"),
            )
            .to("cuda")
            .eval()
        )
        return KPipeline(lang_code="a", repo_id=settings.tts_model_id, model=model)
    except Exception as exc:
        raise ValueError("tts_model_unavailable") from exc


def run(
    input_paths: list[Path],
    output_dir: Path,
    voice: str = "af_heart",
    speed: float = 1.0,
    output_format: str = "mp3",
    max_characters: int | None = None,
    bill_credits: bool = False,
    progress: Callable[[int], None] | None = None,
) -> ToolOutput:
    del bill_credits
    if len(input_paths) != 1:
        raise ValueError("exactly_one_text_file_required")
    if voice not in _SUPPORTED_VOICES:
        raise ValueError("unsupported_voice")
    if not 0.7 <= speed <= 1.3:
        raise ValueError("speech_speed_out_of_range")
    if output_format not in {"wav", "mp3"}:
        raise ValueError("unsupported_audio_format")
    try:
        text = input_paths[0].read_text(encoding="utf-8-sig").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("invalid_text_file") from exc
    if not text or "\x00" in text:
        raise ValueError("text_is_empty_or_invalid")
    if max_characters is not None and len(text) > max_characters:
        raise ValueError("text_character_limit_exceeded")
    if len(text) > 100_000:
        raise ValueError("text_character_limit_exceeded")

    settings = get_settings()
    try:
        import numpy as np
        import soundfile as sf
        from huggingface_hub import hf_hub_download

        pipeline = _load_pipeline()
        voice_path = hf_hub_download(
            repo_id=settings.tts_model_id,
            filename=f"voices/{voice}.pt",
            revision=settings.tts_model_revision,
        )
        voice_tensor = pipeline.load_voice(voice_path)
    except ValueError:
        raise
    except ImportError as exc:
        raise ValueError("tts_runtime_unavailable") from exc
    except Exception as exc:
        raise ValueError("tts_voice_unavailable") from exc

    wav_path = output_dir / "speech.wav"
    consumed = 0
    chunks_written = 0
    try:
        with sf.SoundFile(
            wav_path, mode="w", samplerate=24_000, channels=1, subtype="PCM_16"
        ) as sink:
            for graphemes, _phonemes, audio in pipeline(
                text,
                voice=voice_tensor,
                speed=speed,
                split_pattern=r"\n+|(?<=[.!?])\s+",
            ):
                samples = (
                    audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
                )
                samples = np.asarray(samples, dtype=np.float32).squeeze()
                if samples.ndim != 1 or samples.size == 0:
                    continue
                sink.write(samples)
                consumed += len(str(graphemes))
                chunks_written += 1
                if progress:
                    progress(min(99, max(1, round(consumed / len(text) * 100))))
    except ValueError:
        raise
    except Exception as exc:
        wav_path.unlink(missing_ok=True)
        raise ValueError("speech_generation_failed") from exc
    if chunks_written == 0 or not wav_path.is_file() or wav_path.stat().st_size == 0:
        wav_path.unlink(missing_ok=True)
        raise ValueError("speech_output_empty")

    if output_format == "wav":
        output = wav_path
        content_type = "audio/wav"
    else:
        output = transcode(
            wav_path,
            output_dir,
            "speech.mp3",
            ["-i", str(wav_path), "-c:a", "libmp3lame", "-q:a", "2", "-f", "mp3"],
            timeout_s=600,
        )
        wav_path.unlink(missing_ok=True)
        content_type = "audio/mpeg"
    if progress:
        progress(100)
    return ToolOutput(output, output.name, content_type)
