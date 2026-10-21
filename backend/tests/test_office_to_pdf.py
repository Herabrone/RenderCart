import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from pypdf import PdfReader, PdfWriter

from rendercart.jobs.tasks import _verify_file
from rendercart.registry.models import ToolOutput
from rendercart.tools.pdf.office_to_pdf import run as office_converter

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _write_package(path: Path, *, external_relationship: bool = False) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types><Override ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document.main+xml"/></Types>',
        )
        archive.writestr("word/document.xml", "<document />")
        if external_relationship:
            archive.writestr(
                "word/_rels/document.xml.rels",
                '<Relationships><Relationship TargetMode="External" '
                'Target="https://127.0.0.1/"/></Relationships>',
            )


def test_ooxml_validation_accepts_matching_docx_and_rejects_mime_mismatch(
    tmp_path: Path,
) -> None:
    document = tmp_path / "sample.docx"
    _write_package(document)

    _verify_file(document, _DOCX)
    with pytest.raises(ValueError, match="invalid_office_document"):
        _verify_file(document, _XLSX)


def test_ooxml_validation_rejects_external_relationships(tmp_path: Path) -> None:
    document = tmp_path / "linked.docx"
    _write_package(document, external_relationship=True)

    with pytest.raises(ValueError, match="external_relationship_not_allowed"):
        _verify_file(document, _DOCX)


def test_ooxml_validation_rejects_macro_payloads(tmp_path: Path) -> None:
    document = tmp_path / "macro.docx"
    _write_package(document)
    with ZipFile(document, "a") as archive:
        archive.writestr("word/vbaProject.bin", b"macro")

    with pytest.raises(ValueError, match="macro_content_not_allowed"):
        _verify_file(document, _DOCX)


def test_ooxml_validation_rejects_excessive_compression_ratio(tmp_path: Path) -> None:
    document = tmp_path / "compressed.docx"
    with ZipFile(document, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "A" * 5_000_000)

    with pytest.raises(ValueError, match="office_archive_compression_ratio_exceeded"):
        _verify_file(document, _DOCX)


def test_ooxml_validation_rejects_path_traversal_entries(tmp_path: Path) -> None:
    document = tmp_path / "traversal.docx"
    with ZipFile(document, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("../document.xml", "<document />")

    with pytest.raises(ValueError, match="invalid_office_archive_path"):
        _verify_file(document, _DOCX)


def test_office_conversion_runs_isolated_headless_profile_and_returns_pdf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "input.docx"
    source.write_bytes(b"test office document")
    monkeypatch.setattr(office_converter.shutil, "which", lambda _binary: "soffice")
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        output_dir = Path(command[command.index("--outdir") + 1])
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        with (output_dir / "input.pdf").open("wb") as output:
            writer.write(output)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(office_converter.subprocess, "run", fake_run)

    result = office_converter.run([source], tmp_path)

    assert isinstance(result, ToolOutput)
    assert result.filename == "converted.pdf"
    assert result.content_type == "application/pdf"
    assert len(PdfReader(result.path).pages) == 1
    assert "--headless" in calls[0]
    assert "--convert-to" in calls[0]
    assert any(argument.startswith("-env:UserInstallation=file://") for argument in calls[0])


def test_office_conversion_reports_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "input.xlsx"
    source.write_bytes(b"test office document")
    monkeypatch.setattr(office_converter.shutil, "which", lambda _binary: "soffice")

    def timeout(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("soffice", 240)

    monkeypatch.setattr(office_converter.subprocess, "run", timeout)
    with pytest.raises(ValueError, match="office_conversion_timeout"):
        office_converter.run([source], tmp_path)


def test_office_conversion_rejects_multiple_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly_one_office_document_required"):
        office_converter.run([tmp_path / "one.docx", tmp_path / "two.docx"], tmp_path)
