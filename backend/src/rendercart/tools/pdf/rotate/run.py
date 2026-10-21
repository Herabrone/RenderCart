from pathlib import Path

from pypdf import PdfReader, PdfWriter

from rendercart.registry.models import ToolOutput
from rendercart.tools.pdf.extract_pages.run import _parse_pages


def run(
    input_paths: list[Path],
    output_dir: Path,
    degrees: int = 90,
    pages: str = "",
) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("rotate PDF accepts one input file")
    if degrees not in {90, 180, 270}:
        raise ValueError("rotation must be 90, 180, or 270 degrees")
    reader = PdfReader(input_paths[0], strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf")
    indexes = set(_parse_pages(pages, len(reader.pages)))
    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        if index in indexes:
            page.rotate(degrees)
        writer.add_page(page)
    output_path = output_dir / "rotated.pdf"
    with output_path.open("wb") as output:
        writer.write(output)
    return ToolOutput(output_path, output_path.name, "application/pdf")
