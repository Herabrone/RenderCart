from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageOps

from rendercart.registry.models import ToolOutput

_POINTS_PER_INCH = 72
_DPI = 150
_FIXED_PAGE_SIZES = {
    "a4": (595.28, 841.89),
    "letter": (612.0, 792.0),
}


def _page_dimensions(image: Image.Image, page_size: str, orientation: str) -> tuple[float, float]:
    if page_size == "image":
        return image.width / _DPI * _POINTS_PER_INCH, image.height / _DPI * _POINTS_PER_INCH
    width, height = _FIXED_PAGE_SIZES[page_size]
    is_landscape = orientation == "landscape" or (
        orientation == "auto" and image.width > image.height
    )
    if is_landscape:
        return height, width
    return width, height


def _fit_image(image: Image.Image, width_pt: float, height_pt: float) -> Image.Image:
    page_width = max(1, round(width_pt / _POINTS_PER_INCH * _DPI))
    page_height = max(1, round(height_pt / _POINTS_PER_INCH * _DPI))
    scale = min(page_width / image.width, page_height / image.height)
    target = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(target, Image.Resampling.LANCZOS) if target != image.size else image
    page = Image.new("RGB", (page_width, page_height), "white")
    left = (page.width - resized.width) // 2
    top = (page.height - resized.height) // 2
    if resized.mode == "RGBA":
        page.paste(resized, (left, top), resized.getchannel("A"))
    else:
        page.paste(resized.convert("RGB"), (left, top))
    if resized is not image:
        resized.close()
    return page


def run(
    input_paths: Sequence[Path],
    output_dir: Path,
    page_size: str = "image",
    orientation: str = "auto",
) -> ToolOutput:
    if not input_paths:
        raise ValueError("at_least_one_image_required")
    if page_size not in {"image", *_FIXED_PAGE_SIZES}:
        raise ValueError("unsupported_page_size")
    if orientation not in {"auto", "portrait", "landscape"}:
        raise ValueError("unsupported_orientation")

    pages: list[Image.Image] = []
    try:
        for path in input_paths:
            with Image.open(path) as source:
                source.seek(0)
                image = ImageOps.exif_transpose(source).convert("RGBA")
            width_pt, height_pt = _page_dimensions(image, page_size, orientation)
            if page_size == "image":
                # Save full pixel dimensions at a fixed 150 DPI, without page padding.
                page = Image.new("RGB", image.size, "white")
                page.paste(image, mask=image.getchannel("A"))
            else:
                page = _fit_image(image, width_pt, height_pt)
            image.close()
            pages.append(page)

        output_path = output_dir / "images.pdf"
        first, *remaining = pages
        first.save(
            output_path,
            format="PDF",
            save_all=True,
            append_images=remaining,
            resolution=_DPI,
        )
    finally:
        for page in pages:
            page.close()

    return ToolOutput(output_path, output_path.name, "application/pdf")
