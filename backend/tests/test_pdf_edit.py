from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from rendercart.tools.pdf.edit.run import run


def _pdf(path: Path, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as output:
        writer.write(output)


def test_pdf_edit_free_result_is_watermarked_and_clean_copy_is_locked(tmp_path: Path) -> None:
    source = tmp_path / "edited.pdf"
    _pdf(source, pages=2)

    result = run([source], tmp_path, preview=True)

    assert result.path.name == "edited-preview.pdf"
    assert result.locked_path is not None
    assert result.locked_filename == "edited.pdf"
    preview = PdfReader(result.path)
    clean = PdfReader(result.locked_path)
    assert len(preview.pages) == len(clean.pages) == 2
    assert "RENDERCART" in (preview.pages[0].extract_text() or "")
    assert "RENDERCART" not in (clean.pages[0].extract_text() or "")


def test_pdf_edit_pro_result_has_no_preview_watermark(tmp_path: Path) -> None:
    source = tmp_path / "edited.pdf"
    _pdf(source)

    result = run([source], tmp_path, preview=False)

    assert result.locked_path is None
    assert result.path.name == "edited.pdf"
    assert "RENDERCART" not in (PdfReader(result.path).pages[0].extract_text() or "")


def test_pdf_edit_rejects_invalid_or_encrypted_pdf(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.pdf"
    invalid.write_text("not a pdf", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid_pdf"):
        run([invalid], tmp_path)

    encrypted = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    with encrypted.open("wb") as output:
        writer.write(output)
    with pytest.raises(ValueError, match="encrypted_pdf_not_supported"):
        run([encrypted], tmp_path)
