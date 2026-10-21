from collections.abc import Sequence
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from rendercart.registry.models import ToolOutput
from rendercart.tools.pdf.extract_pages.run import _parse_pages


def run(input_paths: Sequence[Path], output_dir: Path, page_order: str = "") -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_pdf_required")
    reader = PdfReader(input_paths[0], strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf")
    indexes = _parse_pages(page_order, len(reader.pages))
    if not indexes:
        raise ValueError("empty_page_selection")
    writer = PdfWriter()
    for index in indexes:
        writer.add_page(reader.pages[index])
    output_path = output_dir / "organized.pdf"
    with output_path.open("wb") as output:
        writer.write(output)
    return ToolOutput(output_path, output_path.name, "application/pdf")
