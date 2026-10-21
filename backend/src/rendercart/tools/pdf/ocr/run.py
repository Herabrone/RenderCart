import subprocess
from collections.abc import Sequence
from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter

from rendercart.registry.models import ToolOutput

_MAX_PAGES_HARD_LIMIT = 200
_MAX_RENDERED_PIXELS = 25_000_000
_SUPPORTED_LANGUAGES = {"eng", "deu", "fra", "spa"}


def _ocr_image_to_pdf(image_path: Path, output_base: Path, language: str, dpi: int) -> Path:
    try:
        subprocess.run(
            [
                "tesseract",
                str(image_path),
                str(output_base),
                "-l",
                language,
                "--dpi",
                str(dpi),
                "pdf",
            ],
            check=True,
            capture_output=True,
            timeout=180,
            cwd=output_base.parent,
        )
    except FileNotFoundError as exc:
        raise ValueError("ocr_engine_unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("ocr_page_timeout") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError("ocr_page_failed") from exc
    output_path = output_base.with_suffix(".pdf")
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise ValueError("ocr_output_missing")
    return output_path


def run(
    input_paths: Sequence[Path],
    output_dir: Path,
    language: str = "eng",
    max_pages: int = 1,
    dpi: int = 200,
) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_pdf_required")
    if language not in _SUPPORTED_LANGUAGES:
        raise ValueError("unsupported_ocr_language")
    if not 100 <= dpi <= 300:
        raise ValueError("dpi_must_be_between_100_and_300")
    if not 1 <= max_pages <= _MAX_PAGES_HARD_LIMIT:
        raise ValueError("pdf_page_limit_exceeded")

    reader = PdfReader(input_paths[0], strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf")
    page_count = len(reader.pages)
    if page_count == 0:
        raise ValueError("pdf_has_no_pages")
    if page_count > max_pages:
        raise ValueError("pdf_page_limit_exceeded")

    document = pdfium.PdfDocument(input_paths[0])
    output = PdfWriter()
    ocr_readers: list[PdfReader] = []
    scale = dpi / 72
    try:
        for page_index, source_page in enumerate(reader.pages):
            searchable_text = source_page.extract_text()
            if searchable_text and searchable_text.strip():
                output.add_page(source_page)
                continue

            page = document[page_index]
            try:
                width, height = page.get_size()
                if width * scale * height * scale > _MAX_RENDERED_PIXELS:
                    raise ValueError("pdf_page_dimensions_exceed_limit")
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    image_path = output_dir / f"ocr-page-{page_index + 1:04}.png"
                    image.save(image_path, format="PNG", optimize=True)
                    image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()

            try:
                ocr_pdf = _ocr_image_to_pdf(
                    image_path,
                    output_dir / f"ocr-page-{page_index + 1:04}",
                    language,
                    dpi,
                )
            finally:
                image_path.unlink(missing_ok=True)
            ocr_reader = PdfReader(ocr_pdf, strict=True)
            if len(ocr_reader.pages) != 1:
                raise ValueError("ocr_generated_invalid_page_count")
            ocr_readers.append(ocr_reader)
            output.add_page(ocr_reader.pages[0])
    finally:
        document.close()

    output_path = output_dir / "searchable.pdf"
    with output_path.open("wb") as destination:
        output.write(destination)
    ocr_readers.clear()
    return ToolOutput(output_path, output_path.name, "application/pdf")
