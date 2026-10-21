from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from rendercart.auth.models import User
from rendercart.auth.service import create_session
from rendercart.core.access import Level
from rendercart.core.guest import encode_guest_id
from rendercart.jobs import router as jobs_router
from rendercart.jobs.models import CreditAccount, CreditLedger, CreditLot, Job, JobState, Upload


def test_guest_job_response_exposes_preview_but_not_locked_result(
    client: TestClient,
    test_session: Session,
) -> None:
    guest_id = "preview-owner"
    job = Job(
        id=uuid4(),
        guest_id=guest_id,
        tool_slug="background-remover",
        state=JobState.SUCCEEDED,
        options={"preview": True},
        input_upload_ids=[],
        output_key="job/preview.png",
        output_filename="preview.png",
        output_content_type="image/png",
        locked_output_key="job/locked/full.png",
        locked_output_filename="full.png",
        locked_output_content_type="image/png",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_session.add(job)
    test_session.commit()
    client.cookies.set("rc_guest", encode_guest_id(guest_id))

    response = client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    result = response.json()
    assert result["locked_preview"] is True
    assert result["can_unlock"] is False
    assert result["download_url"]
    assert "locked_output_key" not in result
    assert "full.png" not in str(result)


def test_signed_in_job_owner_gets_preview_unlock_offer(
    client: TestClient,
    test_session: Session,
) -> None:
    user = User(email="preview-owner@example.com")
    test_session.add(user)
    test_session.flush()
    raw_session, _session = create_session(test_session, user, None, None, True)
    job = Job(
        id=uuid4(),
        user_id=user.id,
        tool_slug="background-remover",
        state=JobState.SUCCEEDED,
        options={"preview": True},
        input_upload_ids=[],
        output_key="job/preview.png",
        output_filename="preview.png",
        output_content_type="image/png",
        locked_output_key="job/locked/full.png",
        locked_output_filename="full.png",
        locked_output_content_type="image/png",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_session.add(job)
    test_session.commit()
    client.cookies.set("rc_session", raw_session)

    response = client.get(f"/api/jobs/{job.id}")

    assert response.status_code == 200
    result = response.json()
    assert result["can_unlock"] is True
    assert result["payment_product"] == "job_s"
    assert "locked_output_key" not in result


def test_ocr_job_overwrites_client_page_limit_with_guest_limit(
    client: TestClient,
    test_session: Session,
    monkeypatch,
) -> None:
    guest_id = "ocr-page-limit-guest"
    upload = Upload(
        id=uuid4(),
        guest_id=guest_id,
        object_key=f"g:{guest_id}/scan.pdf",
        filename="scan.pdf",
        content_type="application/pdf",
        size_bytes=100,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_session.add(upload)
    test_session.commit()
    client.cookies.set("rc_guest", encode_guest_id(guest_id))
    monkeypatch.setattr(jobs_router, "increment_window", lambda *_args: 1)
    monkeypatch.setattr(jobs_router, "verify_turnstile", lambda *_args: True)
    monkeypatch.setattr(jobs_router, "reserve_counter", lambda *_args: True)
    monkeypatch.setattr(jobs_router.celery_app, "send_task", lambda *_args, **_kwargs: None)

    csrf_token = client.get("/api/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/tools/pdf-ocr/jobs",
        json={
            "upload_ids": [str(upload.id)],
            "options": {"max_pages": 200, "bill_credits": True},
        },
        headers={"X-RC-CSRF": csrf_token},
    )

    assert response.status_code == 202
    job = test_session.get(Job, UUID(response.json()["job_id"]))
    assert job is not None
    assert job.options["max_pages"] == 1
    assert job.options["bill_credits"] is False


def test_batch_job_requires_pro(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(jobs_router, "verify_turnstile", lambda *_args: True)
    monkeypatch.setattr(jobs_router, "increment_window", lambda *_args: 1)
    client.cookies.set("rc_guest", encode_guest_id("batch-guest"))
    csrf_token = client.get("/api/auth/csrf").json()["csrf_token"]

    response = client.post(
        "/api/tools/office-to-pdf/jobs",
        json={"upload_ids": [str(uuid4()), str(uuid4())], "batch_mode": True},
        headers={"X-RC-CSRF": csrf_token},
    )

    assert response.status_code == 402
    assert response.headers["X-Paywall"] == "pro-required"


def test_free_user_cannot_select_paid_resume_layout(
    client: TestClient,
    monkeypatch,
) -> None:
    client.cookies.set("rc_guest", encode_guest_id("resume-layout-guest"))
    monkeypatch.setattr(jobs_router, "verify_turnstile", lambda *_args: True)
    monkeypatch.setattr(jobs_router, "increment_window", lambda *_args: 1)
    csrf_token = client.get("/api/auth/csrf").json()["csrf_token"]

    response = client.post(
        "/api/tools/resume-builder/jobs",
        json={
            "upload_ids": [],
            "options": {
                "template": "modern",
                "resume_json": '{"name":"Avery Example","summary":"Designer."}',
            },
        },
        headers={"X-RC-CSRF": csrf_token},
    )

    assert response.status_code == 402
    assert response.headers["X-Paywall"] == "pro-required"


def test_free_user_cannot_request_ai_resume_rewrite(
    client: TestClient,
    monkeypatch,
) -> None:
    client.cookies.set("rc_guest", encode_guest_id("resume-ai-guest"))
    monkeypatch.setattr(jobs_router, "verify_turnstile", lambda *_args: True)
    monkeypatch.setattr(jobs_router, "increment_window", lambda *_args: 1)
    csrf_token = client.get("/api/auth/csrf").json()["csrf_token"]

    response = client.post(
        "/api/tools/resume-builder/jobs",
        json={
            "upload_ids": [],
            "options": {
                "rewrite_with_ai": True,
                "resume_json": '{"name":"Avery Example","summary":"Designer."}',
            },
        },
        headers={"X-RC-CSRF": csrf_token},
    )

    assert response.status_code == 402
    assert response.headers["X-Paywall"] == "pro-required"


def test_pro_user_can_select_paid_resume_layout(
    client: TestClient,
    test_session: Session,
    monkeypatch,
) -> None:
    user = User(email="resume-layout-pro@example.com")
    test_session.add(user)
    test_session.flush()
    raw_session, _session = create_session(test_session, user, None, None, True)
    grant = CreditLedger(user_id=user.id, amount=2, kind="grant")
    account = CreditAccount(user_id=user.id, balance=2, held=0)
    test_session.add_all([grant, account])
    test_session.flush()
    test_session.add(
        CreditLot(
            user_id=user.id,
            source_ledger_id=grant.id,
            total=2,
            remaining=2,
            held=0,
        )
    )
    test_session.commit()
    client.cookies.set("rc_session", raw_session)
    monkeypatch.setattr(jobs_router, "user_level", lambda *_args: Level.PRO)
    monkeypatch.setattr(jobs_router, "reserve_counter", lambda *_args: True)
    monkeypatch.setattr(jobs_router.celery_app, "send_task", lambda *_args, **_kwargs: None)
    csrf_token = client.get("/api/auth/csrf").json()["csrf_token"]

    response = client.post(
        "/api/tools/resume-builder/jobs",
        json={
            "upload_ids": [],
            "options": {
                "template": "modern",
                "rewrite_with_ai": True,
                "resume_json": '{"name":"Avery Example","summary":"Designer."}',
            },
        },
        headers={"X-RC-CSRF": csrf_token},
    )

    assert response.status_code == 202
    job = test_session.get(Job, UUID(response.json()["job_id"]))
    assert job is not None
    assert job.options["template"] == "modern"
    assert job.options["rewrite_with_ai"] is True
    assert job.charged_credits == 2
    assert test_session.get(CreditAccount, user.id).held == 2


def test_pro_batch_job_accepts_many_files_and_sets_server_option(
    client: TestClient,
    test_session: Session,
    monkeypatch,
) -> None:
    user = User(email="batch-pro@example.com")
    test_session.add(user)
    test_session.flush()
    raw_session, _ = create_session(test_session, user, None, None, True)
    uploads = [
        Upload(
            id=uuid4(),
            user_id=user.id,
            object_key=f"u:{user.id}/{index}.docx",
            filename=f"{index}.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=100,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        for index in range(2)
    ]
    test_session.add_all(uploads)
    test_session.commit()
    client.cookies.set("rc_session", raw_session)
    monkeypatch.setattr(jobs_router, "user_level", lambda *_args: Level.PRO)
    monkeypatch.setattr(jobs_router, "reserve_counter", lambda *_args: True)
    monkeypatch.setattr(jobs_router.celery_app, "send_task", lambda *_args, **_kwargs: None)
    csrf_token = client.get("/api/auth/csrf").json()["csrf_token"]

    response = client.post(
        "/api/tools/office-to-pdf/jobs",
        json={"upload_ids": [str(upload.id) for upload in uploads], "batch_mode": True},
        headers={"X-RC-CSRF": csrf_token},
    )

    assert response.status_code == 202
    job = test_session.get(Job, UUID(response.json()["job_id"]))
    assert job is not None
    assert job.options["batch_mode"] is True


def test_static_credit_cost_is_reserved_for_each_batch_input(
    client: TestClient,
    test_session: Session,
    monkeypatch,
) -> None:
    user = User(email="batch-credits@example.com")
    test_session.add(user)
    test_session.flush()
    raw_session, _ = create_session(test_session, user, None, None, True)
    grant = CreditLedger(user_id=user.id, amount=10, kind="grant")
    account = CreditAccount(user_id=user.id, balance=10, held=0)
    test_session.add_all([grant, account])
    test_session.flush()
    lot = CreditLot(
        user_id=user.id,
        source_ledger_id=grant.id,
        total=10,
        remaining=10,
        held=0,
    )
    uploads = [
        Upload(
            id=uuid4(),
            user_id=user.id,
            object_key=f"u:{user.id}/{index}.pdf",
            filename=f"{index}.pdf",
            content_type="application/pdf",
            size_bytes=100,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        for index in range(2)
    ]
    test_session.add_all([lot, *uploads])
    test_session.commit()
    client.cookies.set("rc_session", raw_session)
    monkeypatch.setattr(jobs_router, "user_level", lambda *_args: Level.PRO)
    monkeypatch.setattr(jobs_router, "reserve_counter", lambda *_args: True)
    monkeypatch.setattr(jobs_router.celery_app, "send_task", lambda *_args, **_kwargs: None)
    csrf_token = client.get("/api/auth/csrf").json()["csrf_token"]

    response = client.post(
        "/api/tools/pdf-to-excel/jobs",
        json={"upload_ids": [str(upload.id) for upload in uploads], "batch_mode": True},
        headers={"X-RC-CSRF": csrf_token},
    )

    assert response.status_code == 202
    job = test_session.get(Job, UUID(response.json()["job_id"]))
    assert job is not None
    assert job.charged_credits == 2
    assert test_session.get(CreditAccount, user.id).held == 2


def test_ocr_job_marks_pro_credit_billing_server_side(
    client: TestClient,
    test_session: Session,
    monkeypatch,
) -> None:
    user = User(email="ocr-pro@example.com")
    test_session.add(user)
    test_session.flush()
    raw_session, _session = create_session(test_session, user, None, None, True)
    upload = Upload(
        id=uuid4(),
        user_id=user.id,
        object_key=f"u:{user.id}/scan.pdf",
        filename="scan.pdf",
        content_type="application/pdf",
        size_bytes=100,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_session.add(upload)
    test_session.commit()
    client.cookies.set("rc_session", raw_session)
    monkeypatch.setattr(jobs_router, "user_level", lambda *_args: Level.PRO)
    monkeypatch.setattr(jobs_router, "increment_window", lambda *_args: 1)
    monkeypatch.setattr(jobs_router, "reserve_counter", lambda *_args: True)
    monkeypatch.setattr(jobs_router.celery_app, "send_task", lambda *_args, **_kwargs: None)

    csrf_token = client.get("/api/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/tools/pdf-ocr/jobs",
        json={"upload_ids": [str(upload.id)], "options": {"bill_credits": False}},
        headers={"X-RC-CSRF": csrf_token},
    )

    assert response.status_code == 202
    job = test_session.get(Job, UUID(response.json()["job_id"]))
    assert job is not None
    assert job.options["bill_credits"] is True
    assert job.charged_credits == 0
