from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rendercart.auth.models import User
from rendercart.jobs.models import (
    CreditAccount,
    CreditLedger,
    CreditLot,
    CreditReservation,
    Job,
    JobState,
)
from rendercart.jobs.tasks import _reserve_dynamic_credits


def _create_credit_job(test_session: Session, balance: int) -> tuple[Job, CreditLot]:
    user = User(email=f"dynamic-{uuid4()}@example.com")
    test_session.add(user)
    test_session.flush()
    grant = CreditLedger(user_id=user.id, amount=balance, kind="grant")
    test_session.add_all([CreditAccount(user_id=user.id, balance=balance), grant])
    test_session.flush()
    lot = CreditLot(
        user_id=user.id,
        source_ledger_id=grant.id,
        total=balance,
        remaining=balance,
        held=0,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    job = Job(
        user_id=user.id,
        tool_slug="pdf-ocr",
        state=JobState.RUNNING,
        options={"bill_credits": True},
        input_upload_ids=[],
        charged_credits=0,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    test_session.add_all([lot, job])
    test_session.flush()
    return job, lot


def test_dynamic_ocr_credits_are_reserved_from_expiring_lots(test_session: Session) -> None:
    job, lot = _create_credit_job(test_session, balance=3)

    _reserve_dynamic_credits(test_session, job, 2)

    account = test_session.get(CreditAccount, job.user_id)
    assert account is not None and account.held == 2
    assert lot.held == 2
    assert job.charged_credits == 2
    reservation = test_session.scalar(
        select(CreditReservation).where(CreditReservation.job_id == job.id)
    )
    assert reservation is not None and reservation.amount == 2


def test_dynamic_credit_shortfall_does_not_create_partial_holds(test_session: Session) -> None:
    job, lot = _create_credit_job(test_session, balance=1)
    account = test_session.get(CreditAccount, job.user_id)
    assert account is not None
    account.balance = 2
    lot.remaining = 1
    test_session.flush()

    with pytest.raises(ValueError, match="insufficient_credits"):
        _reserve_dynamic_credits(test_session, job, 2)

    account = test_session.get(CreditAccount, job.user_id)
    assert account is not None and account.held == 0
    assert lot.held == 0
    assert job.charged_credits == 0
    assert (
        test_session.scalar(select(CreditReservation).where(CreditReservation.job_id == job.id))
        is None
    )
