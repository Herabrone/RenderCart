from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pypdf import PdfWriter
from sqlalchemy import select

from rendercart.jobs.models import AuditLog, Job, JobState
from rendercart.jobs.tasks import _finish_job
from rendercart.tools.pdf.esign.run import run


def _pdf(path: Path, *, metadata: dict[str, str] | None = None, pages: int = 1) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if metadata:
        writer.add_metadata(metadata)
    with path.open("wb") as output:
        writer.write(output)


def test_esign_copies_signed_pdf_and_returns_audit_hashes(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    signed = tmp_path / "signed-input.pdf"
    _pdf(source)
    _pdf(signed, metadata={"/Title": "Visually signed by Test User"})

    result = run(
        [source, signed],
        tmp_path,
        signer_name="Test User",
        signer_email="test@example.com",
        page_number=1,
        consented=True,
        signer_ip="192.0.2.1",
        signed_at=datetime.now(UTC).isoformat(),
    )

    assert result.path.read_bytes() == signed.read_bytes()
    assert result.audit_event is not None
    assert result.audit_event["action"] == "pdf.esign.completed"
    assert result.audit_event["signer_email"] == "test@example.com"
    assert result.audit_event["signer_ip"] == "192.0.2.1"
    assert result.audit_event["source_sha256"] != result.audit_event["signed_sha256"]


@pytest.mark.parametrize(
    ("signed_pages", "consented", "page_number", "error"),
    [
        (1, False, 1, "signing_consent_required"),
        (1, True, 2, "invalid_signature_page"),
        (2, True, 1, "signed_document_page_count_mismatch"),
    ],
)
def test_esign_rejects_invalid_signing_inputs(
    tmp_path: Path, signed_pages: int, consented: bool, page_number: int, error: str
) -> None:
    source = tmp_path / "source.pdf"
    signed = tmp_path / "signed-input.pdf"
    _pdf(source)
    _pdf(signed, metadata={"/Title": "different"}, pages=signed_pages)

    with pytest.raises(ValueError, match=error):
        run(
            [source, signed],
            tmp_path,
            signer_name="Test User",
            signer_email="test@example.com",
            page_number=page_number,
            consented=consented,
            signer_ip="192.0.2.1",
            signed_at=datetime.now(UTC).isoformat(),
        )


def test_esign_rejects_unchanged_document(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    _pdf(source)

    with pytest.raises(ValueError, match="signature_output_unchanged"):
        run(
            [source, source],
            tmp_path,
            signer_name="Test User",
            signer_email="test@example.com",
            page_number=1,
            consented=True,
            signer_ip="192.0.2.1",
            signed_at=datetime.now(UTC).isoformat(),
        )


def test_esign_audit_record_survives_job_deletion(
    test_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import rendercart.jobs.tasks as tasks

    monkeypatch.setattr(tasks, "_publish", lambda *_args: None)
    job = Job(
        id=uuid4(),
        tool_slug="esign-pdf",
        state=JobState.RUNNING,
        input_upload_ids=[],
        guest_id="guest-test",
        expires_at=datetime.now(UTC),
    )
    test_session.add(job)
    test_session.commit()

    _finish_job(
        test_session,
        job,
        f"{job.id}/signed.pdf",
        "signed.pdf",
        "application/pdf",
        audit_event={
            "action": "pdf.esign.completed",
            "event_type": "visual_signature",
            "signer_email": "test@example.com",
            "source_sha256": "a" * 64,
            "signed_sha256": "b" * 64,
        },
    )
    audit = test_session.scalar(select(AuditLog).where(AuditLog.target == str(job.id)))
    assert audit is not None
    assert audit.action == "pdf.esign.completed"
    assert audit.details["source_sha256"] == "a" * 64

    test_session.delete(job)
    test_session.commit()
    assert test_session.scalar(select(AuditLog).where(AuditLog.target == str(job.id))) is not None
