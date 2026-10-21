from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
import stripe
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from rendercart.auth.models import User
from rendercart.billing import router as billing_router
from rendercart.billing.models import DayPass, Purchase, StripeEvent
from rendercart.core.config import Settings
from rendercart.jobs.models import (
    CreditAccount,
    CreditLedger,
    CreditLot,
    CreditReservation,
    Job,
    JobDispatch,
    JobState,
)


def test_guest_day_pass_fulfilled_once_and_claimable(
    client: TestClient,
    test_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    purchase = Purchase(
        id=uuid4(),
        guest_id="guest-123",
        email="buyer@example.com",
        kind="day_pass",
        product_key="day_pass",
        amount_cents=299,
        credits_granted=150,
        status="pending",
    )
    test_session.add(purchase)
    test_session.commit()

    event_data = {
        "id": "evt_guest_day_pass",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_guest_day_pass",
                "mode": "payment",
                "payment_status": "paid",
                "currency": "usd",
                "amount_subtotal": 299,
                "payment_intent": "pi_guest_day_pass",
                "customer": "cus_guest_day_pass",
                "metadata": {"rendercart_purchase_id": str(purchase.id)},
            }
        },
    }
    settings = Settings(stripe_webhook_secret=SecretStr("whsec_test"))
    monkeypatch.setattr(billing_router, "get_settings", lambda: settings)
    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        lambda *_args, **_kwargs: SimpleNamespace(to_dict_recursive=lambda: event_data),
    )
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        billing_router,
        "send_auth_link",
        lambda email, token, purpose: sent.append((email, token, purpose)),
    )

    first = client.post(
        "/api/billing/webhook", content=b"{}", headers={"Stripe-Signature": "valid"}
    )
    duplicate = client.post(
        "/api/billing/webhook", content=b"{}", headers={"Stripe-Signature": "valid"}
    )

    assert first.status_code == 200
    assert first.json() == {"received": True, "duplicate": False}
    assert duplicate.status_code == 200
    assert duplicate.json() == {"received": True, "duplicate": True}
    assert test_session.scalar(select(func.count()).select_from(StripeEvent)) == 1
    assert test_session.scalar(select(func.count()).select_from(DayPass)) == 1
    assert test_session.scalar(select(func.count()).select_from(CreditLedger)) == 1
    account = test_session.scalar(select(CreditAccount))
    assert account is not None and account.balance == 150
    user = test_session.scalar(select(User).where(User.email == "buyer@example.com"))
    assert user is not None and user.email_verified_at is None
    assert len(sent) == 1 and sent[0][0] == user.email and sent[0][2] == "magic_link"

    csrf_response = client.get("/api/auth/csrf")
    signed_in = client.post(
        "/api/auth/magic",
        json={"token": sent[0][1]},
        headers={"X-RC-CSRF": csrf_response.json()["csrf_token"]},
    )
    assert signed_in.status_code == 200
    assert signed_in.json()["email_verified"] is True


def test_subscription_retry_window_keeps_pro_access() -> None:
    from rendercart.core.access import AccessSubject, Level, effective_level

    level = effective_level(
        AccessSubject(
            subscription_status="past_due",
            subscription_period_end=datetime(2026, 11, 1, tzinfo=UTC),
        ),
        datetime(2026, 10, 18, tzinfo=UTC),
    )
    assert level == Level.PRO


def test_paid_job_webhook_releases_job_through_outbox(
    test_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(email="paid-job@example.com", email_verified_at=datetime.now(UTC))
    test_session.add(user)
    test_session.flush()
    job = Job(
        user_id=user.id,
        guest_id=None,
        tool_slug="merge-pdf",
        payment_tier="job_s",
        state=JobState.AWAITING_PAYMENT,
        options={},
        input_upload_ids=[],
        quota_reserved=False,
        quota_key=None,
        expires_at=datetime.now(UTC),
    )
    test_session.add(job)
    test_session.flush()
    purchase = Purchase(
        user_id=user.id,
        job_id=job.id,
        kind="single_job",
        product_key="job_s",
        amount_cents=99,
        credits_granted=0,
        status="pending",
    )
    test_session.add(purchase)
    test_session.flush()

    billing_router._process_checkout(
        test_session,
        {
            "id": "cs_paid_job",
            "mode": "payment",
            "payment_status": "paid",
            "currency": "usd",
            "amount_subtotal": 99,
            "payment_intent": "pi_paid_job",
            "metadata": {"rendercart_purchase_id": str(purchase.id)},
        },
    )

    assert job.state == JobState.QUEUED
    dispatch = test_session.get(JobDispatch, job.id)
    assert dispatch is not None and dispatch.dispatched_at is None
    assert purchase.status == "paid"
    test_session.commit()

    from rendercart.jobs import tasks as job_tasks

    task_sessions = sessionmaker(bind=test_session.get_bind(), expire_on_commit=False)
    sent_tasks: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(job_tasks, "SessionLocal", task_sessions)
    monkeypatch.setattr(
        job_tasks.app,
        "send_task",
        lambda name, **kwargs: sent_tasks.append((name, kwargs)),
    )
    assert job_tasks.dispatch_paid_jobs() == 1
    test_session.expire_all()
    dispatch = test_session.get(JobDispatch, job.id)
    assert dispatch is not None and dispatch.dispatched_at is not None
    assert len(sent_tasks) == 1
    assert sent_tasks[0][0] == "rendercart.jobs.tasks.execute_tool"


def test_preview_payment_unlocks_stored_full_result_without_rerunning(
    test_session: Session,
) -> None:
    user = User(email="preview-buyer@example.com", email_verified_at=datetime.now(UTC))
    test_session.add(user)
    test_session.flush()
    job = Job(
        user_id=user.id,
        tool_slug="background-remover",
        payment_tier="job_s",
        state=JobState.SUCCEEDED,
        options={"preview": True},
        input_upload_ids=[],
        output_key="preview-job/background-removed-preview.png",
        output_filename="background-removed-preview.png",
        output_content_type="image/png",
        locked_output_key="preview-job/locked/background-removed-full.png",
        locked_output_filename="background-removed-full.png",
        locked_output_content_type="image/png",
        expires_at=datetime.now(UTC),
    )
    test_session.add(job)
    test_session.flush()
    purchase = Purchase(
        user_id=user.id,
        job_id=job.id,
        kind="single_job",
        product_key="job_s",
        amount_cents=99,
        credits_granted=0,
        status="pending",
    )
    test_session.add(purchase)
    test_session.flush()

    billing_router._process_checkout(
        test_session,
        {
            "id": "cs_preview_unlock",
            "mode": "payment",
            "payment_status": "paid",
            "currency": "usd",
            "amount_subtotal": 99,
            "payment_intent": "pi_preview_unlock",
            "metadata": {"rendercart_purchase_id": str(purchase.id)},
        },
    )

    assert job.state == JobState.SUCCEEDED
    assert job.output_key == "preview-job/locked/background-removed-full.png"
    assert job.output_filename == "background-removed-full.png"
    assert job.locked_output_key is None
    assert test_session.get(JobDispatch, job.id) is None
    assert purchase.status == "paid"


def test_credit_expiry_preserves_held_amount_until_job_releases(
    test_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rendercart.jobs import tasks as job_tasks

    user = User(email="credits@example.com")
    test_session.add(user)
    test_session.flush()
    account = CreditAccount(user_id=user.id, balance=120, held=40)
    grant = CreditLedger(user_id=user.id, amount=120, kind="grant")
    test_session.add_all([account, grant])
    test_session.flush()
    lot = CreditLot(
        user_id=user.id,
        source_ledger_id=grant.id,
        total=120,
        remaining=120,
        held=40,
        expires_at=datetime(2026, 10, 17, tzinfo=UTC),
    )
    test_session.add(lot)
    job = Job(
        user_id=user.id,
        tool_slug="sample-tool",
        state=JobState.RUNNING,
        options={},
        input_upload_ids=[],
        expires_at=datetime(2026, 10, 19, tzinfo=UTC),
    )
    test_session.add(job)
    test_session.flush()
    test_session.add(CreditReservation(job_id=job.id, credit_lot_id=lot.id, amount=40))
    test_session.commit()

    task_sessions = sessionmaker(bind=test_session.get_bind(), expire_on_commit=False)
    monkeypatch.setattr(job_tasks, "SessionLocal", task_sessions)
    assert job_tasks.expire_credits() == 1
    test_session.expire_all()
    assert test_session.get(CreditAccount, user.id).balance == 40  # type: ignore[union-attr]
    assert test_session.get(CreditLot, lot.id).remaining == 40  # type: ignore[union-attr]

    lot = test_session.get(CreditLot, lot.id)
    account = test_session.get(CreditAccount, user.id)
    assert lot is not None and account is not None
    lot.held = 0
    account.held = 0
    test_session.commit()
    assert job_tasks.expire_credits() == 1
    test_session.expire_all()
    assert test_session.get(CreditAccount, user.id).balance == 0  # type: ignore[union-attr]
    assert job_tasks.expire_credits() == 0
