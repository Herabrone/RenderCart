from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from rendercart.core.config import get_settings
from rendercart.registry.models import ToolOutput

_MODEL_INPUT_SIZE = (1024, 1024)
_PREVIEW_PIXEL_LIMIT = 250_000
_MAX_INPUT_PIXELS = 16_000_000


@lru_cache(maxsize=1)
def _load_model() -> tuple[Any, Any, Any]:
    import numpy as np
    import torch
    from transformers import AutoModelForImageSegmentation

    if not torch.cuda.is_available():
        raise RuntimeError("gpu_unavailable")
    settings = get_settings()
    model = AutoModelForImageSegmentation.from_pretrained(
        settings.birefnet_model_id,
        revision=settings.birefnet_model_revision,
        trust_remote_code=True,
    )
    model.to("cuda")
    model.eval()
    return model, torch, np


def _infer_mask(image: Image.Image) -> Image.Image:
    model, torch, numpy = _load_model()
    resized = image.resize(_MODEL_INPUT_SIZE, Image.Resampling.BILINEAR)
    values = numpy.asarray(resized, dtype=numpy.float32) / 255.0
    tensor = torch.from_numpy(values.copy()).permute(2, 0, 1)
    mean = torch.tensor([0.485, 0.456, 0.406], dtype=tensor.dtype).view(3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], dtype=tensor.dtype).view(3, 1, 1)
    tensor = ((tensor - mean) / std).unsqueeze(0).to("cuda")
    with torch.inference_mode():
        prediction = model(tensor)[-1].sigmoid()[0, 0].float().cpu().numpy()
    mask_values = numpy.clip(prediction * 255, 0, 255).astype(numpy.uint8)
    return Image.fromarray(mask_values, mode="L").resize(image.size, Image.Resampling.LANCZOS)


def run(input_paths: list[Path], output_dir: Path, preview: bool = True) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_image_required")
    with Image.open(input_paths[0]) as uploaded:
        source = ImageOps.exif_transpose(uploaded).convert("RGB")
    if source.width * source.height > _MAX_INPUT_PIXELS:
        raise ValueError("image_exceeds_16_megapixels")
    mask = _infer_mask(source)
    source.putalpha(mask)
    full_path = output_dir / "background-removed-full.png"
    source.save(full_path, format="PNG", optimize=True)
    if not preview:
        return ToolOutput(full_path, full_path.name, "image/png")

    preview_image = source
    if source.width * source.height > _PREVIEW_PIXEL_LIMIT:
        scale = (_PREVIEW_PIXEL_LIMIT / (source.width * source.height)) ** 0.5
        preview_size = (max(1, int(source.width * scale)), max(1, int(source.height * scale)))
        preview_image = source.resize(preview_size, Image.Resampling.LANCZOS)
    preview_path = output_dir / "background-removed-preview.png"
    preview_image.save(preview_path, format="PNG", optimize=True)
    return ToolOutput(
        preview_path,
        preview_path.name,
        "image/png",
        locked_path=full_path,
        locked_filename=full_path.name,
        locked_content_type="image/png",
    )
