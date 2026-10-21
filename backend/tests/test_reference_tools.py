from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas

from rendercart.jobs.options import decrypt_sensitive_options, encrypt_sensitive_options
from rendercart.tools.image.background_remover import run as background_remover
from rendercart.tools.image.converter.run import run as convert_image
from rendercart.tools.pdf.compress.run import run as compress_pdf
from rendercart.tools.pdf.extract_pages.run import run as extract_pages
from rendercart.tools.pdf.from_images.run import run as images_to_pdf
from rendercart.tools.pdf.merge.run import run as merge_pdfs
from rendercart.tools.pdf.organize.run import run as organize_pdf
from rendercart.tools.pdf.protect.manifest import TOOL as protect_pdf_tool
from rendercart.tools.pdf.protect.run import run as protect_pdf
from rendercart.tools.pdf.rotate.run import run as rotate_pdf
from rendercart.tools.pdf.split.run import run as split_pdf
from rendercart.tools.pdf.to_excel import run as pdf_to_excel
from rendercart.tools.pdf.to_images.run import run as pdf_to_images
from rendercart.tools.pdf.to_word import run as pdf_to_word


@pytest.fixture
def sample_pdfs(tmp_path: Path) -> list[Path]:
    paths = []
    for index in range(2):
        path = tmp_path / f"page-{index}.pdf"
        canvas = Canvas(str(path), pagesize=(612, 792))
        canvas.drawString(72, 720, f"golden-page-{index + 1}")
        canvas.save()
        paths.append(path)
    return paths


def test_merge_pdf_combines_all_inputs(tmp_path: Path, sample_pdfs: list[Path]) -> None:
    result = merge_pdfs(sample_pdfs, tmp_path, "Combined")

    assert result.path.exists()
    pages = PdfReader(result.path).pages
    assert len(pages) == 2
    assert [page.extract_text().strip() for page in pages] == ["golden-page-1", "golden-page-2"]


def test_merge_pdf_requires_two_inputs(tmp_path: Path, sample_pdfs: list[Path]) -> None:
    with pytest.raises(ValueError, match="at least two"):
        merge_pdfs(sample_pdfs[:1], tmp_path)


def test_image_converter_creates_webp(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(source)

    result = convert_image([source], tmp_path, "WEBP")

    with Image.open(result.path) as converted:
        assert converted.format == "WEBP"
        assert converted.size == (2, 2)


def test_image_converter_rejects_unknown_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="PNG, JPEG, or WEBP"):
        convert_image([tmp_path / "missing.png"], tmp_path, "TIFF")


def test_background_remover_creates_low_resolution_transparent_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "photo.png"
    Image.new("RGB", (1000, 500), "blue").save(source)
    monkeypatch.setattr(
        background_remover,
        "_infer_mask",
        lambda image: Image.new("L", image.size, 127),
    )

    result = background_remover.run([source], tmp_path, preview=True)

    with Image.open(result.path) as output:
        assert output.mode == "RGBA"
        assert output.width * output.height <= 250_000
        assert output.getpixel((10, 10))[3] == 127
    assert result.locked_path is not None
    with Image.open(result.locked_path) as full_output:
        assert full_output.size == (1000, 500)


def test_background_remover_keeps_full_resolution_when_paid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "photo.png"
    Image.new("RGB", (1000, 500), "blue").save(source)
    monkeypatch.setattr(
        background_remover,
        "_infer_mask",
        lambda image: Image.new("L", image.size, 255),
    )

    result = background_remover.run([source], tmp_path, preview=False)
    assert result.locked_path is None
    with Image.open(result.path) as output:
        assert output.size == (1000, 500)


def test_extract_pdf_pages_keeps_requested_pages(tmp_path: Path) -> None:
    source = tmp_path / "three-pages.pdf"
    writer = PdfWriter()
    for page in range(3):
        writer.add_blank_page(width=612 + page, height=792)
    with source.open("wb") as output:
        writer.write(output)

    result = extract_pages([source], tmp_path, "1, 3")
    extracted = PdfReader(result.path)
    assert len(extracted.pages) == 2
    assert extracted.pages[1].mediabox.width == 614


def test_extract_pdf_pages_rejects_out_of_range_selection(
    tmp_path: Path, sample_pdfs: list[Path]
) -> None:
    with pytest.raises(ValueError, match="page_number_out_of_range"):
        extract_pages([sample_pdfs[0]], tmp_path, "99")


def test_rotate_pdf_rotates_selected_pages(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    with source.open("wb") as output:
        writer.write(output)

    result = rotate_pdf([source], tmp_path, 90, "2")
    rotated = PdfReader(result.path)
    assert rotated.pages[0].rotation == 0
    assert rotated.pages[1].rotation == 90


def test_organize_pdf_reorders_and_removes_pages(tmp_path: Path) -> None:
    source = tmp_path / "three-pages.pdf"
    writer = PdfWriter()
    for width in (612, 613, 614):
        writer.add_blank_page(width=width, height=792)
    with source.open("wb") as output:
        writer.write(output)

    result = organize_pdf([source], tmp_path, "3, 1")
    organized = PdfReader(result.path)
    assert [page.mediabox.width for page in organized.pages] == [614, 612]


def test_compress_pdf_rewrites_valid_document(tmp_path: Path, sample_pdfs: list[Path]) -> None:
    result = compress_pdf([sample_pdfs[0]], tmp_path)
    pages = PdfReader(result.path).pages
    assert len(pages) == 1
    assert "golden-page-1" in (pages[0].extract_text() or "")


def test_protect_pdf_requires_password_to_open(tmp_path: Path, sample_pdfs: list[Path]) -> None:
    result = protect_pdf([sample_pdfs[0]], tmp_path, "correct horse battery")
    protected = PdfReader(result.path)
    assert protected.is_encrypted
    assert protected.decrypt("correct horse battery") in {1, 2}
    assert len(protected.pages) == 1
    assert "golden-page-1" in (protected.pages[0].extract_text() or "")


def test_protect_pdf_rejects_short_password(tmp_path: Path, sample_pdfs: list[Path]) -> None:
    with pytest.raises(ValueError, match="password_must_be"):
        protect_pdf([sample_pdfs[0]], tmp_path, "short")


def test_protect_pdf_password_is_encrypted_in_job_options() -> None:
    stored = encrypt_sensitive_options(protect_pdf_tool, {"password": "long enough password"})
    assert stored["password"] != "long enough password"
    assert isinstance(stored["password"], str) and stored["password"].startswith("enc:")
    assert decrypt_sensitive_options(protect_pdf_tool, stored) == {
        "password": "long enough password"
    }


def test_pdf_to_excel_exports_detected_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pages = [
        SimpleNamespace(
            extract_tables=lambda: [[["Name", "Value"], ["alpha", "3"], [" =1+1", "safe"]]]
        ),
        SimpleNamespace(extract_tables=lambda: []),
    ]

    class FakePdf:
        def __enter__(self) -> FakePdf:
            self.pages = pages
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(pdf_to_excel.pdfplumber, "open", lambda _path: FakePdf())
    result = pdf_to_excel.run([tmp_path / "input.pdf"], tmp_path, "1")

    assert (
        result.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(result.path, read_only=True)
    assert list(workbook.active.values) == [
        ("Name", "Value"),
        ("alpha", "3"),
        ("' =1+1", "safe"),
    ]
    workbook.close()


def test_pdf_to_excel_rejects_documents_without_detected_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakePdf:
        pages = [SimpleNamespace(extract_tables=lambda: [])]

        def __enter__(self) -> FakePdf:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(pdf_to_excel.pdfplumber, "open", lambda _path: FakePdf())
    with pytest.raises(ValueError, match="no_tables_found"):
        pdf_to_excel.run([tmp_path / "input.pdf"], tmp_path)


def test_pdf_to_images_exports_all_pages_as_zip(tmp_path: Path) -> None:
    source = tmp_path / "two-pages.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    with source.open("wb") as output:
        writer.write(output)

    result = pdf_to_images([source], tmp_path, dpi=72)
    assert result.content_type == "application/zip"
    with ZipFile(result.path) as archive:
        assert archive.namelist() == ["page-0001.png", "page-0002.png"]


def test_split_pdf_creates_page_groups(tmp_path: Path) -> None:
    source = tmp_path / "three-pages.pdf"
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=612, height=792)
    with source.open("wb") as output:
        writer.write(output)

    result = split_pdf([source], tmp_path, pages_per_file=2)
    with ZipFile(result.path) as archive:
        assert archive.namelist() == ["pages-0001-0002.pdf", "pages-0003-0003.pdf"]
        first_split = PdfReader(archive.open(archive.namelist()[0]))
        assert len(first_split.pages) == 2


def test_pdf_to_images_exports_single_page_as_png(tmp_path: Path, sample_pdfs: list[Path]) -> None:
    result = pdf_to_images([sample_pdfs[0]], tmp_path, dpi=72)
    with Image.open(result.path) as image:
        assert image.format == "PNG"
        assert image.size == (612, 792)


def test_pdf_to_images_preserves_page_appearance(tmp_path: Path) -> None:
    source = tmp_path / "colored.pdf"
    canvas = Canvas(str(source), pagesize=(72, 72))
    canvas.setFillColor(colors.red)
    canvas.rect(0, 0, 72, 72, fill=1, stroke=0)
    canvas.save()

    result = pdf_to_images([source], tmp_path, dpi=72)

    with Image.open(result.path) as image:
        red, green, blue = image.convert("RGB").getpixel((36, 36))
        assert red > 240 and green < 20 and blue < 20


def test_pdf_to_word_preserves_text_and_page_breaks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self, *, layout: bool) -> str:
            assert layout is True
            return self.text

    class FakePdf:
        pages = [FakePage("First page\nR&D <report>"), FakePage("Second page")]

        def __enter__(self) -> FakePdf:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(pdf_to_word.pdfplumber, "open", lambda _path: FakePdf())
    result = pdf_to_word.run([tmp_path / "input.pdf"], tmp_path)

    with ZipFile(result.path) as archive:
        document_xml = archive.read("word/document.xml")
    assert b"First page" in document_xml
    assert b"R&amp;D &lt;report&gt;" in document_xml
    assert b"Second page" in document_xml
    assert document_xml.count(b'w:type="page"') == 1


def test_pdf_to_word_extracts_text_from_a_real_pdf(tmp_path: Path) -> None:
    source = tmp_path / "text.pdf"
    canvas = Canvas(str(source), pagesize=(612, 792))
    canvas.drawString(72, 720, "RenderCart PDF export golden fixture")
    canvas.save()

    result = pdf_to_word.run([source], tmp_path)

    with ZipFile(result.path) as archive:
        document_xml = archive.read("word/document.xml")
    assert b"RenderCart PDF export golden fixture" in document_xml


def test_pdf_to_word_rejects_scanned_pdf_without_ocr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakePage:
        def extract_text(self, *, layout: bool) -> None:
            return None

    class FakePdf:
        pages = [FakePage()]

        def __enter__(self) -> FakePdf:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(pdf_to_word.pdfplumber, "open", lambda _path: FakePdf())
    with pytest.raises(ValueError, match="no_selectable_text_found"):
        pdf_to_word.run([tmp_path / "input.pdf"], tmp_path)


def test_images_to_pdf_combines_images_and_fits_a4_pages(tmp_path: Path) -> None:
    first = tmp_path / "wide.png"
    second = tmp_path / "portrait.png"
    Image.new("RGBA", (600, 300), (255, 0, 0, 128)).save(first)
    Image.new("RGB", (300, 600), "blue").save(second)

    result = images_to_pdf([first, second], tmp_path, page_size="a4")

    reader = PdfReader(result.path)
    assert len(reader.pages) == 2
    assert round(float(reader.pages[0].mediabox.width)) == 842
    assert round(float(reader.pages[0].mediabox.height)) == 595


def test_images_to_pdf_rejects_empty_input(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at_least_one_image_required"):
        images_to_pdf([], tmp_path)
