from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from rendercart.core.db import Base


class DynamicQrCode(Base):
    __tablename__ = "dynamic_qr_codes"
    __table_args__ = (Index("ix_dynamic_qr_owner_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    target_url: Mapped[str] = mapped_column(String(2048))
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    scan_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class VaultShortLink(Base):
    __tablename__ = "vault_short_links"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    target_url_enc: Mapped[str] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class VaultPaste(Base):
    __tablename__ = "vault_pastes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    content_enc: Mapped[str] = mapped_column(Text)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class VaultFileShare(Base):
    __tablename__ = "vault_file_shares"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    object_key_enc: Mapped[str] = mapped_column(Text)
    filename_enc: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DynamicQrScan(Base):
    __tablename__ = "dynamic_qr_scans"
    __table_args__ = (Index("ix_dynamic_qr_scans_code_time", "qr_id", "scanned_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    qr_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dynamic_qr_codes.id", ondelete="SET NULL"), index=True
    )
    qr_code: Mapped[str] = mapped_column(String(32), nullable=False)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), default="ZZ", nullable=False)
    device_type: Mapped[str] = mapped_column(String(16), default="unknown", nullable=False)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )


class DynamicQrReport(Base):
    __tablename__ = "dynamic_qr_reports"
    __table_args__ = (
        Index("ix_dynamic_qr_reports_created", "created_at"),
        Index("ix_dynamic_qr_reports_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    qr_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dynamic_qr_codes.id", ondelete="SET NULL"), index=True
    )
    qr_code: Mapped[str] = mapped_column(String(32), nullable=False)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    message: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(16), default="open", nullable=False)
    resolved_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SavedInvoiceClient(Base):
    __tablename__ = "saved_invoice_clients"
    __table_args__ = (Index("ix_saved_invoice_clients_owner_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    encrypted_data: Mapped[str] = mapped_column(String(4096))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SavedInvoiceItem(Base):
    __tablename__ = "saved_invoice_items"
    __table_args__ = (Index("ix_saved_invoice_items_owner_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    encrypted_data: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class InvoiceNumberSequence(Base):
    __tablename__ = "invoice_number_sequences"
    __table_args__ = (
        UniqueConstraint("user_id", "document_type", name="uq_invoice_number_owner_type"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(16))
    next_value: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RecurringInvoiceSchedule(Base):
    __tablename__ = "recurring_invoice_schedules"
    __table_args__ = (Index("ix_recurring_invoice_due", "active", "next_run_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    interval: Mapped[str] = mapped_column(String(16))
    anchor_day: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    encrypted_invoice_json: Mapped[str] = mapped_column(String(32_768))
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UptimeMonitor(Base):
    __tablename__ = "uptime_monitors"
    __table_args__ = (
        Index("ix_uptime_monitors_due", "active", "next_check_at"),
        Index("ix_uptime_monitors_owner", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    target_url: Mapped[str] = mapped_column(String(2048))
    alert_email: Mapped[str] = mapped_column(String(320))
    alert_webhook_enc: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    alert_sms_enc: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    alert_sms_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    outage_generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=900, nullable=False)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    outage_alert_sent: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UptimeMonitorCheck(Base):
    __tablename__ = "uptime_monitor_checks"
    __table_args__ = (Index("ix_uptime_monitor_checks_monitor_time", "monitor_id", "checked_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    monitor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("uptime_monitors.id", ondelete="SET NULL"), index=True, nullable=True
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)


class UptimeMonitorSmsUsage(Base):
    __tablename__ = "uptime_monitor_sms_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "period", name="uq_uptime_monitor_sms_usage_owner_period"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    sent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class UptimeMonitorSmsDelivery(Base):
    __tablename__ = "uptime_monitor_sms_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "monitor_id", "outage_generation", "event", name="uq_monitor_sms_delivery_event"
        ),
        Index("ix_monitor_sms_delivery_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    monitor_id: Mapped[UUID] = mapped_column(
        ForeignKey("uptime_monitors.id", ondelete="CASCADE"), index=True
    )
    outage_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    event: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    credit_lot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("credit_lots.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DomainExpiryAlert(Base):
    __tablename__ = "domain_expiry_alerts"
    __table_args__ = (
        Index("ix_domain_expiry_alerts_due", "active", "next_check_at"),
        Index("ix_domain_expiry_alerts_owner", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    domain: Mapped[str] = mapped_column(String(253))
    alert_email: Mapped[str] = mapped_column(String(320))
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=86_400, nullable=False)
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tls_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    domain_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tls_error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    domain_error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tls_alerted_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    domain_alerted_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class WebhookBin(Base):
    __tablename__ = "webhook_bins"
    __table_args__ = (
        Index("ix_webhook_bins_owner_expiry", "user_id", "expires_at"),
        Index("ix_webhook_bins_expiry", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_prefix: Mapped[str] = mapped_column(String(12))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WebhookBinEvent(Base):
    __tablename__ = "webhook_bin_events"
    __table_args__ = (Index("ix_webhook_bin_events_bin_received", "bin_id", "received_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    bin_id: Mapped[UUID] = mapped_column(
        ForeignKey("webhook_bins.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[str] = mapped_column(String(10))
    payload_enc: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WebsiteAuditReport(Base):
    __tablename__ = "website_audit_reports"
    __table_args__ = (Index("ix_website_audit_reports_owner_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    target_url_enc: Mapped[str] = mapped_column(Text)
    scores: Mapped[dict[str, object]] = mapped_column(JSON)
    metrics: Mapped[dict[str, object]] = mapped_column(JSON)
    findings: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WebsiteAuditSchedule(Base):
    __tablename__ = "website_audit_schedules"
    __table_args__ = (
        Index("ix_website_audit_schedules_due", "active", "next_run_at"),
        Index("ix_website_audit_schedules_owner_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_url_enc: Mapped[str] = mapped_column(Text)
    device: Mapped[str] = mapped_column(String(16), default="mobile", nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    last_error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
