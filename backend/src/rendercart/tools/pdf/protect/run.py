from collections.abc import Sequence
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from rendercart.registry.models import ToolOutput


def run(input_paths: Sequence[Path], output_dir: Path, password: str) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_pdf_required")
    if not 8 <= len(password) <= 128:
        raise ValueError("password_must_be_8_to_128_characters")

    reader = PdfReader(input_paths[0], strict=True)
    if reader.is_encrypted:
        raise ValueError("encrypted_pdf_not_supported")
    writer = PdfWriter(clone_from=reader)
    writer.encrypt(user_password=password, owner_password=None, algorithm="AES-256")
    output_path = output_dir / "protected.pdf"
    with output_path.open("wb") as output:
        writer.write(output)
    return ToolOutput(output_path, output_path.name, "application/pdf")
