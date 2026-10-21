from pathlib import Path

from pypdf import PdfReader, PdfWriter

from rendercart.registry.models import ToolOutput


def _parse_pages(specification: str, total_pages: int) -> list[int]:
    if not specification.strip():
        return list(range(total_pages))
    indexes: list[int] = []
    for chunk in specification.split(","):
        part = chunk.strip()
        if not part:
            raise ValueError("invalid_page_selection")
        bounds = part.split("-")
        if len(bounds) == 1:
            start = end = int(bounds[0])
        elif len(bounds) == 2:
            start, end = (int(bound) for bound in bounds)
        else:
            raise ValueError("invalid_page_selection")
        if start < 1 or end < start or end > total_pages:
            raise ValueError("page_number_out_of_range")
        indexes.extend(range(start - 1, end))
    if len(set(indexes)) != len(indexes):
        raise ValueError("duplicate_page_selection")
    return indexes


def run(input_paths: list[Path], output_dir: Path, pages: str = "") -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("extract pages accepts one PDF")
    reader = PdfReader(input_paths[0], strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf")
    indexes = _parse_pages(pages, len(reader.pages))
    if not indexes:
        raise ValueError("empty_page_selection")
    writer = PdfWriter()
    for index in indexes:
        writer.add_page(reader.pages[index])
    output_path = output_dir / "extracted-pages.pdf"
    with output_path.open("wb") as output:
        writer.write(output)
    return ToolOutput(output_path, output_path.name, "application/pdf")
