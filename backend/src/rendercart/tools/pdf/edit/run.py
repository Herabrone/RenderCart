from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.pdfgen.canvas import Canvas

from rendercart.registry.models import ToolOutput


def _validate_pdf(path: Path) -> PdfReader:
    with path.open("rb") as source:
        if source.read(5) != b"%PDF-":
            raise ValueError("invalid_pdf")
    reader = PdfReader(path, strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf_not_supported")
    if not reader.pages:
        raise ValueError("empty_pdf")
    return reader


def _watermarked_copy(reader: PdfReader, output_path: Path) -> None:
    writer = PdfWriter()
    writer.append(reader)
    for page in writer.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        stream = BytesIO()
        canvas = Canvas(stream, pagesize=(width, height), pageCompression=1)
        canvas.saveState()
        canvas.setFillColor(Color(0.42, 0.34, 0.62, alpha=0.42))
        canvas.setFont("Helvetica-Bold", max(14, min(28, width / 22)))
        canvas.drawCentredString(width / 2, height * 0.06, "RENDERCART · FREE PREVIEW")
        canvas.restoreState()
        canvas.save()
        overlay = PdfReader(BytesIO(stream.getvalue()), strict=True).pages[0]
        page.merge_page(overlay)
    with output_path.open("wb") as output:
        writer.write(output)


def run(input_paths: list[Path], output_dir: Path, preview: bool = True) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_pdf_required")
    reader = _validate_pdf(input_paths[0])
    clean_path = output_dir / "edited.pdf"
    if preview:
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        with clean_path.open("wb") as output:
            writer.write(output)
        preview_path = output_dir / "edited-preview.pdf"
        _watermarked_copy(PdfReader(clean_path, strict=True), preview_path)
        return ToolOutput(
            preview_path,
            preview_path.name,
            "application/pdf",
            locked_path=clean_path,
            locked_filename=clean_path.name,
            locked_content_type="application/pdf",
        )
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    with clean_path.open("wb") as output:
        writer.write(output)
    return ToolOutput(clean_path, clean_path.name, "application/pdf")
