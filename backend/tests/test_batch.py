from pathlib import Path
from zipfile import ZipFile

import pytest
from pypdf import PdfWriter

from rendercart.jobs.batch import credits_for_inputs, execution_timeout, run_batch
from rendercart.registry.models import Category, Runtime, SeoMeta, ToolManifest, ToolOutput


def _tool(tmp_path: Path, calls: list[list[str]], *, slug: str = "compress-pdf") -> ToolManifest:
    def runner(input_paths: list[Path], output_dir: Path) -> ToolOutput:
        calls.append([path.name for path in input_paths])
        output = output_dir / "result.pdf"
        output.write_bytes(f"converted {len(calls)}".encode())
        return ToolOutput(output, output.name, "application/pdf")

    return ToolManifest(
        slug=slug,
        name="Test PDF tool",
        category=Category.PDF,
        summary="Test batch processing.",
        batchable=True,
        runtime=Runtime.CPU,
        seo=SeoMeta(title="Test", description="Test"),
        runner=runner,
    )


def test_batch_processes_each_input_and_writes_a_named_zip(tmp_path: Path) -> None:
    inputs = [tmp_path / "one.pdf", tmp_path / "two.pdf", tmp_path / "three.pdf"]
    for path in inputs:
        path.write_bytes(b"input")
    calls: list[list[str]] = []

    result = run_batch(_tool(tmp_path, calls), inputs, tmp_path, {})

    assert calls == [["one.pdf"], ["two.pdf"], ["three.pdf"]]
    with ZipFile(result.path) as archive:
        assert archive.namelist() == [
            "001-one/result.pdf",
            "002-two/result.pdf",
            "003-three/result.pdf",
        ]


def test_batch_merge_processes_inputs_as_ordered_pairs(tmp_path: Path) -> None:
    inputs = [tmp_path / f"{index}.pdf" for index in range(4)]
    for path in inputs:
        path.write_bytes(b"input")
    calls: list[list[str]] = []

    result = run_batch(_tool(tmp_path, calls, slug="merge-pdf"), inputs, tmp_path, {})

    assert calls == [["0.pdf", "1.pdf"], ["2.pdf", "3.pdf"]]
    with ZipFile(result.path) as archive:
        assert archive.namelist() == ["merge-001/result.pdf", "merge-002/result.pdf"]


def test_batch_merge_rejects_unpaired_input(tmp_path: Path) -> None:
    inputs = [tmp_path / "one.pdf", tmp_path / "two.pdf", tmp_path / "three.pdf"]
    for path in inputs:
        path.write_bytes(b"input")

    with pytest.raises(ValueError, match="batch_merge_requires_file_pairs"):
        run_batch(_tool(tmp_path, [], slug="merge-pdf"), inputs, tmp_path, {})


def test_dynamic_page_credits_round_up_for_each_document(tmp_path: Path) -> None:
    from rendercart.tools.pdf.ocr.manifest import TOOL as ocr_pdf

    inputs = [tmp_path / "five-a.pdf", tmp_path / "five-b.pdf"]
    for path in inputs:
        writer = PdfWriter()
        for _ in range(5):
            writer.add_blank_page(width=612, height=792)
        with path.open("wb") as output:
            writer.write(output)

    assert credits_for_inputs(ocr_pdf, inputs) == 2


def test_batch_timeout_scales_with_independent_runs(tmp_path: Path) -> None:
    tool = _tool(tmp_path, [])

    assert execution_timeout(tool, 4, batch_mode=True) == tool.timeout_s * 4
    assert (
        execution_timeout(_tool(tmp_path, [], slug="merge-pdf"), 4, batch_mode=True)
        == tool.timeout_s * 2
    )
    assert execution_timeout(tool, 4, batch_mode=False) == tool.timeout_s
