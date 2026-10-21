from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from rendercart.tools.pdf.ocr import run as pdf_ocr


def _write_blank_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as output:
        writer.write(output)


def test_ocr_generates_one_output_page_per_scanned_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "scan.pdf"
    _write_blank_pdf(source, 2)
    calls: list[tuple[str, int]] = []

    def fake_ocr(image_path: Path, output_base: Path, language: str, dpi: int) -> Path:
        assert image_path.is_file()
        calls.append((language, dpi))
        output_path = output_base.with_suffix(".pdf")
        _write_blank_pdf(output_path, 1)
        return output_path

    monkeypatch.setattr(pdf_ocr, "_ocr_image_to_pdf", fake_ocr)

    result = pdf_ocr.run([source], tmp_path, language="eng", max_pages=2)

    assert len(PdfReader(result.path).pages) == 2
    assert calls == [("eng", 200), ("eng", 200)]


def test_tesseract_is_called_in_searchable_pdf_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")
    output_base = tmp_path / "ocr-output"
    call: dict[str, object] = {}

    def fake_run(args: list[str], **kwargs: object) -> None:
        call["args"] = args
        call["kwargs"] = kwargs
        output_base.with_suffix(".pdf").write_bytes(b"pdf")

    monkeypatch.setattr(pdf_ocr.subprocess, "run", fake_run)

    result = pdf_ocr._ocr_image_to_pdf(image_path, output_base, "deu", 240)

    assert result == output_base.with_suffix(".pdf")
    assert call["args"] == [
        "tesseract",
        str(image_path),
        str(output_base),
        "-l",
        "deu",
        "--dpi",
        "240",
        "pdf",
    ]
    kwargs = call["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["check"] is True
    assert kwargs["timeout"] == 180


def test_ocr_refuses_to_exceed_access_level_page_limit(tmp_path: Path) -> None:
    source = tmp_path / "too-many-pages.pdf"
    _write_blank_pdf(source, 2)

    with pytest.raises(ValueError, match="pdf_page_limit_exceeded"):
        pdf_ocr.run([source], tmp_path, max_pages=1)


def test_ocr_rejects_unsupported_language_before_processing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported_ocr_language"):
        pdf_ocr.run([tmp_path / "unused.pdf"], tmp_path, language="../../eng")
