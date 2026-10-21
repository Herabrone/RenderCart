from __future__ import annotations

import hashlib
import shutil
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

from rendercart.registry.models import ToolOutput


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def run(
    input_paths: Sequence[Path],
    output_dir: Path,
    signer_name: str,
    signer_email: str,
    page_number: int,
    consented: bool,
    signer_ip: str,
    signed_at: str,
) -> ToolOutput:
    if len(input_paths) != 2:
        raise ValueError("source_and_signed_pdf_required")
    if not consented:
        raise ValueError("signing_consent_required")
    if not signer_name.strip() or len(signer_name) > 120:
        raise ValueError("signer_name_required")
    if not 1 <= page_number:
        raise ValueError("invalid_signature_page")
    try:
        timestamp = datetime.fromisoformat(signed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_signing_timestamp") from exc
    if timestamp.tzinfo is None:
        raise ValueError("invalid_signing_timestamp")

    source_reader = PdfReader(input_paths[0], strict=True)
    signed_reader = PdfReader(input_paths[1], strict=True)
    if source_reader.is_encrypted or signed_reader.is_encrypted:
        raise ValueError("encrypted_pdf_not_supported")
    if not source_reader.pages or len(source_reader.pages) != len(signed_reader.pages):
        raise ValueError("signed_document_page_count_mismatch")
    if page_number > len(source_reader.pages):
        raise ValueError("invalid_signature_page")
    for source_page, signed_page in zip(source_reader.pages, signed_reader.pages, strict=True):
        if source_page.mediabox != signed_page.mediabox:
            raise ValueError("signed_document_page_size_mismatch")

    source_hash = _sha256(input_paths[0])
    signed_hash = _sha256(input_paths[1])
    if source_hash == signed_hash:
        raise ValueError("signature_output_unchanged")
    output_path = output_dir / "signed.pdf"
    shutil.copyfile(input_paths[1], output_path)
    event: dict[str, object] = {
        "action": "pdf.esign.completed",
        "event_type": "visual_signature",
        "signer_name": signer_name.strip(),
        "signer_email": signer_email,
        "signer_ip": signer_ip,
        "signed_at": timestamp.isoformat(),
        "page_number": page_number,
        "source_sha256": source_hash,
        "signed_sha256": signed_hash,
    }
    return ToolOutput(
        output_path,
        output_path.name,
        "application/pdf",
        audit_event=event,
    )
