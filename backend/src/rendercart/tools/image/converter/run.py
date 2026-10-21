from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageOps

from rendercart.registry.models import ToolOutput


def run(input_paths: Sequence[Path], output_dir: Path, output_format: str) -> ToolOutput:
    normalized_format = output_format.upper()
    if normalized_format not in {"PNG", "JPEG", "WEBP"}:
        raise ValueError("output format must be PNG, JPEG, or WEBP")
    if len(input_paths) != 1:
        raise ValueError("image converter accepts one input image")
    suffix, content_type = {
        "PNG": (".png", "image/png"),
        "JPEG": (".jpg", "image/jpeg"),
        "WEBP": (".webp", "image/webp"),
    }[normalized_format]
    output_path = output_dir / f"converted{suffix}"
    with Image.open(input_paths[0]) as source:
        image = ImageOps.exif_transpose(source)
        if normalized_format == "JPEG" and image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.save(output_path, format=normalized_format)
    return ToolOutput(output_path, output_path.name, content_type)
