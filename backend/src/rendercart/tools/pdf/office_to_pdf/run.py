from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import quote

from pypdf import PdfReader

from rendercart.registry.models import ToolOutput

_SUPPORTED_SUFFIXES = {".docx", ".xlsx", ".pptx"}
_OUTPUT_LIMIT = 1_073_741_824


def run(input_paths: Sequence[Path], output_dir: Path) -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("exactly_one_office_document_required")
    source = input_paths[0]
    if source.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise ValueError("unsupported_office_document")
    executable = shutil.which(os.environ.get("LIBREOFFICE_BIN", "soffice"))
    if not executable:
        raise ValueError("office_converter_unavailable")

    destination = output_dir / "office-pdf-output"
    profile = output_dir / "office-profile"
    destination.mkdir(mode=0o700)
    profile.mkdir(mode=0o700)
    profile_uri = quote(profile.as_posix(), safe="/:")
    command = [
        executable,
        "--headless",
        "--nologo",
        "--nodefault",
        "--nolockcheck",
        "--norestore",
        f"-env:UserInstallation=file://{profile_uri}",
        "--convert-to",
        "pdf",
        "--outdir",
        str(destination),
        str(source),
    ]
    env = {
        "HOME": str(profile),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": os.environ.get("PATH", ""),
        "SAL_USE_VCLPLUGIN": "gen",
        "TMPDIR": str(profile),
    }
    try:
        completed = subprocess.run(
            command,
            cwd=output_dir,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=240,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("office_conversion_timeout") from exc
    if completed.returncode != 0:
        raise ValueError("office_conversion_failed")

    converted = destination / f"{source.stem}.pdf"
    if not converted.is_file() or converted.stat().st_size == 0:
        raise ValueError("office_conversion_failed")
    if converted.stat().st_size > _OUTPUT_LIMIT:
        raise ValueError("converted_pdf_too_large")
    try:
        reader = PdfReader(converted, strict=True)
        if reader.is_encrypted or not reader.pages:
            raise ValueError("invalid_converted_pdf")
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("invalid_converted_pdf") from exc

    output_path = output_dir / "converted.pdf"
    shutil.move(str(converted), output_path)
    return ToolOutput(output_path, output_path.name, "application/pdf")
