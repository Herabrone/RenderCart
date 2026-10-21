from collections.abc import Sequence
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from pypdf import PdfReader, PdfWriter

from rendercart.registry.models import ToolOutput


def run(input_paths: Sequence[Path], output_dir: Path, pages_per_file: int = 1) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_pdf_required")
    if not 1 <= pages_per_file <= 100:
        raise ValueError("pages_per_file_must_be_between_1_and_100")
    reader = PdfReader(input_paths[0], strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf")
    if len(reader.pages) < 2:
        raise ValueError("split_requires_multiple_pages")

    output_paths: list[Path] = []
    total_pages = len(reader.pages)
    for start in range(0, total_pages, pages_per_file):
        end = min(start + pages_per_file, total_pages)
        writer = PdfWriter()
        for page_index in range(start, end):
            writer.add_page(reader.pages[page_index])
        path = output_dir / f"pages-{start + 1:04}-{end:04}.pdf"
        with path.open("wb") as output:
            writer.write(output)
        output_paths.append(path)

    archive_path = output_dir / "split-pdf.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in output_paths:
            archive.write(path, path.name)
            path.unlink()
    return ToolOutput(archive_path, archive_path.name, "application/zip")
