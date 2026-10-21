from collections.abc import Sequence
from pathlib import Path

from pypdf import PdfWriter

from rendercart.registry.models import ToolOutput


def run(
    input_paths: Sequence[Path], output_dir: Path, bookmark_title: str | None = None
) -> ToolOutput:
    if len(input_paths) < 2:
        raise ValueError("at least two PDF files are required")
    writer = PdfWriter()
    for path in input_paths:
        writer.append(path)
    if bookmark_title:
        writer.add_outline_item(bookmark_title, 0)
    output_path = output_dir / "merged.pdf"
    with output_path.open("wb") as output:
        writer.write(output)
    return ToolOutput(output_path, output_path.name, "application/pdf")
