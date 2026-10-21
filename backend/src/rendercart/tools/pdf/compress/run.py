from collections.abc import Sequence
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from rendercart.registry.models import ToolOutput


def run(input_paths: Sequence[Path], output_dir: Path, preset: str = "balanced") -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_pdf_required")
    if preset not in {"balanced", "maximum"}:
        raise ValueError("invalid_compression_preset")

    reader = PdfReader(input_paths[0], strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf_not_supported")
    writer = PdfWriter(clone_from=reader)
    writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    stream_level = 9 if preset == "maximum" else 6
    for page in writer.pages:
        page.compress_content_streams(level=stream_level)
    writer.add_metadata({"/Producer": "RenderCart PDF optimizer"})
    output_path = output_dir / "compressed.pdf"
    with output_path.open("wb") as output:
        writer.write(output)
    if output_path.stat().st_size >= input_paths[0].stat().st_size:
        # Keep a valid output even when the source was already efficiently encoded.
        return ToolOutput(output_path, output_path.name, "application/pdf")
    return ToolOutput(output_path, output_path.name, "application/pdf")
