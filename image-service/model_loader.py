from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import torch
from diffusers import StableDiffusionXLImg2ImgPipeline

from config import settings, resolve_model_registry

logger = logging.getLogger(__name__)

MODEL_REGISTRY = resolve_model_registry()
DEFAULT_MODEL_ID = settings.default_model_id or MODEL_REGISTRY.get("default_model")


def get_model_entry(model_id: Optional[str] = None) -> Dict[str, Any]:
    model_id = model_id or DEFAULT_MODEL_ID
    models = MODEL_REGISTRY.get("models", {})
    model_entry = models.get(model_id)
    if not model_entry:
        raise ValueError(f"Unknown model id '{model_id}' in model registry")
    return model_entry


def _resolve_model_path(model_entry: Dict[str, Any]) -> Path:
    local_path = model_entry.get("local_path")
    if not local_path:
        raise ValueError("Local path is not configured for the selected model entry")

    path = Path(local_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / path
    if not path.exists():
        raise FileNotFoundError(f"Local model path not found: {path}")
    return path


def load_pipeline(model_id: Optional[str] = None) -> StableDiffusionXLImg2ImgPipeline:
    model_entry = get_model_entry(model_id)
    logger.info("Loading generation model", extra={"model_id": model_entry.get("id"), "source": model_entry.get("source")})

    model_ref = None
    local_files_only = False
    if model_entry.get("source") == "local":
        try:
            model_ref = _resolve_model_path(model_entry)
            local_files_only = True
        except FileNotFoundError as exc:
            fallback = model_entry.get("pretrained_id")
            if fallback:
                logger.warning(
                    "Local model path not found; falling back to pretrained Hugging Face identifier",
                    extra={"local_path": model_entry.get("local_path"), "fallback_id": fallback},
                )
                model_ref = fallback
                local_files_only = False
            else:
                raise
    else:
        model_ref = model_entry.get("pretrained_id")

    if model_ref is None:
        raise ValueError("No model reference configured for the selected model entry")

    pipeline = StableDiffusionXLImg2ImgPipeline.from_pretrained(
        str(model_ref),
        torch_dtype=getattr(torch, model_entry.get("torch_dtype", "float16")),
        variant=model_entry.get("variant", "fp16"),
        local_files_only=local_files_only,
    )

    pipeline.enable_model_cpu_offload()
    pipeline.enable_attention_slicing()
    pipeline.enable_vae_slicing()
    pipeline.enable_vae_tiling()

    logger.info("Generation pipeline loaded", extra={"model_id": model_entry.get("id")})
    return pipeline


def get_default_pipeline() -> StableDiffusionXLImg2ImgPipeline:
    return load_pipeline(DEFAULT_MODEL_ID)
