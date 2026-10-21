from collections.abc import Sequence
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pypdfium2 as pdfium

from rendercart.registry.models import ToolOutput


def run(input_paths: Sequence[Path], output_dir: Path, dpi: int = 150) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_pdf_required")
    if not 72 <= dpi <= 300:
        raise ValueError("dpi_must_be_between_72_and_300")
    document = pdfium.PdfDocument(input_paths[0])
    if len(document) == 0:
        raise ValueError("pdf_has_no_pages")
    if len(document) > 200:
        raise ValueError("pdf_page_limit_exceeded")

    scale = dpi / 72
    rendered: list[Path] = []
    try:
        for page_index in range(len(document)):
            page = document[page_index]
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            output_path = output_dir / f"page-{page_index + 1:04}.png"
            image.save(output_path, format="PNG", optimize=True)
            rendered.append(output_path)
            image.close()
            bitmap.close()
            page.close()
    finally:
        document.close()

    if len(rendered) == 1:
        return ToolOutput(rendered[0], rendered[0].name, "image/png")

    archive_path = output_dir / "pdf-pages.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for image_path in rendered:
            archive.write(image_path, image_path.name)
            image_path.unlink()
    return ToolOutput(archive_path, archive_path.name, "application/zip")
