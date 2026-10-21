from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from rendercart.core.db import Base


class JobState(StrEnum):
    AWAITING_PAYMENT = "awaiting_payment"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Upload(Base):
    __tablename__ = "uploads"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    guest_id: Mapped[str | None] = mapped_column(String(64), index=True)
    object_key: Mapped[str] = mapped_column(String(512), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(127))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_owner_created", "user_id", "created_at"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    guest_id: Mapped[str | None] = mapped_column(String(64), index=True)
    tool_slug: Mapped[str] = mapped_column(String(80), index=True)
    payment_tier: Mapped[str | None] = mapped_column(String(16))
    charged_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state: Mapped[JobState] = mapped_column(
        Enum(
            JobState,
            native_enum=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        default=JobState.QUEUED,
        index=True,
    )
    options: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    input_upload_ids: Mapped[list[str]] = mapped_column(JSON)
    output_key: Mapped[str | None] = mapped_column(String(512))
    output_filename: Mapped[str | None] = mapped_column(String(255))
    output_content_type: Mapped[str | None] = mapped_column(String(127))
    locked_output_key: Mapped[str | None] = mapped_column(String(512))
    locked_output_filename: Mapped[str | None] = mapped_column(String(255))
    locked_output_content_type: Mapped[str | None] = mapped_column(String(127))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    quota_reserved: Mapped[bool] = mapped_column(Boolean, default=False)
    quota_key: Mapped[str | None] = mapped_column(String(255))
    duration_quota_key: Mapped[str | None] = mapped_column(String(255))
    duration_quota_reserved_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    word_quota_key: Mapped[str | None] = mapped_column(String(255))
    word_quota_reserved_words: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class JobDispatch(Base):
    """Transactional outbox for jobs released after a confirmed single-job payment."""

    __tablename__ = "job_dispatches"

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class CreditAccount(Base):
    __tablename__ = "credit_accounts"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    balance: Mapped[int] = mapped_column(Integer, default=0)
    held: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CreditLedger(Base):
    __tablename__ = "credit_ledger"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), index=True
    )
    amount: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24))
    reference_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CreditLot(Base):
    __tablename__ = "credit_lots"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_ledger_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_ledger.id", ondelete="CASCADE"), unique=True
    )
    total: Mapped[int] = mapped_column(Integer)
    remaining: Mapped[int] = mapped_column(Integer)
    held: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CreditReservation(Base):
    __tablename__ = "credit_reservations"

    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    credit_lot_id: Mapped[UUID] = mapped_column(
        ForeignKey("credit_lots.id", ondelete="CASCADE"), primary_key=True
    )
    amount: Mapped[int] = mapped_column(Integer)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolOverride(Base):
    __tablename__ = "tool_overrides"
    slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    limits: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    prices: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
