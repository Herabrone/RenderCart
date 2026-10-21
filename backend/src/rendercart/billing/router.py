import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, cast
from uuid import UUID, uuid4

import stripe
import structlog
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from rendercart.auth import service as auth_service
from rendercart.auth.email import send_auth_link
from rendercart.auth.models import TokenPurpose, User
from rendercart.auth.router import require_csrf
from rendercart.billing.access import user_level
from rendercart.billing.models import DayPass, Purchase, StripeEvent, Subscription
from rendercart.core.config import Settings, get_settings
from rendercart.core.db import get_db
from rendercart.core.guest import decode_guest_id
from rendercart.jobs.models import (
    AuditLog,
    CreditAccount,
    CreditLedger,
    CreditLot,
    Job,
    JobDispatch,
    JobState,
    ToolOverride,
)
from rendercart.registry.loader import load_builtin_registry

router = APIRouter(prefix="/api/billing", tags=["billing"])
Db = Annotated[Session, Depends(get_db)]
logger = structlog.get_logger(__name__)
registry = load_builtin_registry()

PRODUCTS: dict[str, tuple[str, str, int, int]] = {
    "pro_monthly": ("subscription", "stripe_price_pro_monthly", 999, 1000),
    "day_pass": ("day_pass", "stripe_price_day_pass", 299, 150),
    "job_s": ("single_job", "stripe_price_job_s", 99, 0),
    "job_m": ("single_job", "stripe_price_job_m", 199, 0),
    "job_l": ("single_job", "stripe_price_job_l", 299, 0),
    "credits_500": ("credit_pack", "stripe_price_credits_500", 499, 500),
    "credits_1500": ("credit_pack", "stripe_price_credits_1500", 1199, 1500),
}


class CheckoutRequest(BaseModel):
    product: Literal[
        "pro_monthly",
        "day_pass",
        "job_s",
        "job_m",
        "job_l",
        "credits_500",
        "credits_1500",
    ]
    email: EmailStr | None = None


class JobCheckoutRequest(BaseModel):
    product: Literal["job_s", "job_m", "job_l"]


def _user_from_cookie(db: Session, raw_session: str | None) -> User:
    result = auth_service.get_session_user(db, raw_session)
    if result is None:
        raise HTTPException(status_code=401, detail="Sign in before purchasing")
    user, _session = result
    if user.is_banned:
        raise HTTPException(status_code=403, detail="Account is unavailable")
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail="Verify your email before purchasing")
    return user


def _stripe_settings() -> Settings:
    settings = get_settings()
    if not settings.stripe_secret_key or not settings.stripe_secret_key.get_secret_value():
        raise HTTPException(status_code=503, detail="Payments are not configured")
    stripe.api_key = settings.stripe_secret_key.get_secret_value()
    return settings


def _product_config(product: str, settings: Settings) -> tuple[str, str, int, int]:
    kind, price_field, default_cents, credits = PRODUCTS[product]
    price_id = getattr(settings, price_field)
    if not price_id:
        raise HTTPException(status_code=503, detail=f"The {product} price is not configured")
    amount_field = {
        "pro_monthly": "pro_monthly_amount_cents",
        "day_pass": "day_pass_amount_cents",
        "job_s": "job_s_amount_cents",
        "job_m": "job_m_amount_cents",
        "job_l": "job_l_amount_cents",
        "credits_500": "credits_500_amount_cents",
        "credits_1500": "credits_1500_amount_cents",
    }[product]
    if product == "pro_monthly":
        credits = settings.pro_monthly_credits
    elif product == "day_pass":
        credits = settings.day_pass_credits
    return kind, price_id, int(getattr(settings, amount_field, default_cents)), credits


def _get_or_create_customer(db: Session, user: User) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id
    try:
        customer = stripe.Customer.create(
            email=user.email,
            name=user.display_name or user.email,
            metadata={"rendercart_user_id": str(user.id)},
            idempotency_key=f"rendercart-customer-{user.id}",
        )
    except stripe.StripeError as exc:
        logger.exception("stripe_customer_creation_failed", user_id=str(user.id))
        raise HTTPException(status_code=502, detail="Could not prepare a billing customer") from exc
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


@router.post("/checkout", dependencies=[Depends(require_csrf)])
def create_checkout(
    payload: CheckoutRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
    raw_guest: Annotated[str | None, Cookie(alias="rc_guest")] = None,
) -> dict[str, str]:
    settings = _stripe_settings()
    user_pair = auth_service.get_session_user(db, raw_session)
    user = user_pair[0] if user_pair else None
    guest_email = str(payload.email).strip().casefold() if payload.email else None
    if user is None and payload.product != "day_pass":
        raise HTTPException(status_code=401, detail="Sign in before purchasing")
    if user and (user.is_banned or user.email_verified_at is None):
        raise HTTPException(status_code=403, detail="Verify your email before purchasing")
    if user is None and not guest_email:
        raise HTTPException(status_code=422, detail="Enter an email address for your day pass")
    if payload.product in {"job_s", "job_m", "job_l"}:
        raise HTTPException(status_code=400, detail="Single-job checkout requires a pending job")
    if payload.product == "pro_monthly":
        assert user is not None
        current_level = user_level(db, user)
        if current_level >= 3:
            raise HTTPException(status_code=409, detail="Your account already has Pro access")
    kind, price_id, amount_cents, credits = _product_config(payload.product, settings)
    customer_id = _get_or_create_customer(db, user) if user else None
    purchase_id = uuid4()
    purchase = Purchase(
        id=purchase_id,
        user_id=user.id if user else None,
        guest_id=decode_guest_id(raw_guest),
        email=user.email if user else guest_email,
        kind=kind,
        product_key=payload.product,
        amount_cents=amount_cents,
        credits_granted=credits,
        status="pending",
    )
    db.add(purchase)
    db.commit()

    mode = "subscription" if payload.product == "pro_monthly" else "payment"
    app_url = settings.app_base_url.rstrip("/")
    params: dict[str, object] = {
        "mode": mode,
        "client_reference_id": str(user.id) if user else str(purchase.id),
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": (
            f"{app_url}/account/billing?status=success&session_id={{CHECKOUT_SESSION_ID}}"
        ),
        "cancel_url": f"{app_url}/pricing?status=cancelled",
        "metadata": {
            "rendercart_user_id": str(user.id) if user else "",
            "rendercart_purchase_id": str(purchase.id),
            "rendercart_product": payload.product,
        },
        "idempotency_key": f"rendercart-checkout-{purchase.id}",
    }
    if customer_id:
        params["customer"] = customer_id
    elif guest_email:
        params["customer_email"] = guest_email
        params["customer_creation"] = "always"
    if settings.stripe_tax_enabled:
        params["automatic_tax"] = {"enabled": True}
        params["billing_address_collection"] = "required"
    if mode == "subscription":
        assert user is not None
        params["subscription_data"] = {
            "metadata": {
                "rendercart_user_id": str(user.id),
                "rendercart_product": payload.product,
            }
        }
    try:
        create_session = cast(Any, stripe.checkout.Session.create)
        session = create_session(**params)
    except stripe.StripeError as exc:
        purchase.status = "failed"
        db.commit()
        logger.exception(
            "stripe_checkout_creation_failed",
            user_id=str(user.id) if user else None,
            product=payload.product,
        )
        raise HTTPException(status_code=502, detail="Could not start checkout") from exc
    purchase.stripe_checkout_session_id = session.id
    db.commit()
    if not session.url:
        raise HTTPException(status_code=502, detail="Stripe did not return a checkout URL")
    return {"url": session.url, "session_id": session.id}


@router.post("/jobs/{job_id}/checkout", dependencies=[Depends(require_csrf)])
def create_single_job_checkout(
    job_id: UUID,
    payload: JobCheckoutRequest,
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, str]:
    settings = _stripe_settings()
    user = _user_from_cookie(db, raw_session)
    job = db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.state == JobState.SUCCEEDED and job.locked_output_key:
        tool = registry.get(job.tool_slug)
        required_product = f"job_{tool.job_tier.value.lower()}" if tool and tool.job_tier else None
        if payload.product != required_product:
            raise HTTPException(status_code=400, detail="Single-job price tier does not match tool")
        if job.payment_tier not in {None, payload.product}:
            raise HTTPException(status_code=409, detail="A different purchase tier is already set")
        job.payment_tier = payload.product
        job.expires_at = datetime.now(UTC) + timedelta(hours=24)
        db.commit()
    elif job.state != JobState.AWAITING_PAYMENT:
        raise HTTPException(status_code=409, detail="This job is not waiting for payment")
    if job.payment_tier != payload.product:
        raise HTTPException(status_code=409, detail="Checkout tier does not match this job")

    tool = registry.get(job.tool_slug)
    if tool is None or tool.job_tier is None:
        raise HTTPException(status_code=409, detail="This tool has no single-job checkout")
    required_product = f"job_{tool.job_tier.value.lower()}"
    if payload.product != required_product:
        raise HTTPException(status_code=400, detail="Single-job price tier does not match tool")

    pending_purchase = db.scalar(
        select(Purchase).where(Purchase.job_id == job.id, Purchase.status == "pending")
    )
    if pending_purchase:
        if pending_purchase.product_key != payload.product:
            raise HTTPException(status_code=409, detail="A checkout already exists for this job")
        if pending_purchase.stripe_checkout_session_id:
            existing_session = stripe.checkout.Session.retrieve(
                pending_purchase.stripe_checkout_session_id
            )
            if existing_session.url:
                return {"url": existing_session.url, "session_id": existing_session.id}

    override = db.get(ToolOverride, job.tool_slug)
    configured_override = (
        override.prices.get(payload.product)
        if override and isinstance(override.prices, dict)
        else None
    )
    if configured_override is not None:
        if (
            isinstance(configured_override, bool)
            or not isinstance(configured_override, int)
            or configured_override < 1
        ):
            raise HTTPException(status_code=503, detail="The tool's single-job price is invalid")
        kind, price_id, amount_cents, credits = "single_job", None, configured_override, 0
    else:
        kind, price_id, amount_cents, credits = _product_config(payload.product, settings)
    customer_id = _get_or_create_customer(db, user)
    purchase = Purchase(
        user_id=user.id,
        job_id=job.id,
        kind=kind,
        product_key=payload.product,
        amount_cents=amount_cents,
        credits_granted=credits,
        status="pending",
    )
    db.add(purchase)
    db.commit()
    base_url = settings.app_base_url.rstrip("/")
    params: dict[str, object] = {
        "mode": "payment",
        "customer": customer_id,
        "client_reference_id": str(user.id),
        "line_items": (
            [
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": amount_cents,
                        "product_data": {"name": f"RenderCart {tool.name} single-job unlock"},
                    },
                    "quantity": 1,
                }
            ]
            if configured_override is not None
            else [{"price": price_id, "quantity": 1}]
        ),
        "success_url": f"{base_url}/jobs/{job.id}?payment=success",
        "cancel_url": f"{base_url}/jobs/{job.id}?payment=cancelled",
        "metadata": {
            "rendercart_user_id": str(user.id),
            "rendercart_purchase_id": str(purchase.id),
            "rendercart_product": payload.product,
            "rendercart_job_id": str(job.id),
        },
        "idempotency_key": f"rendercart-single-job-{purchase.id}",
    }
    if settings.stripe_tax_enabled:
        params["automatic_tax"] = {"enabled": True}
        params["billing_address_collection"] = "required"
    try:
        create_session = cast(Any, stripe.checkout.Session.create)
        checkout_session = create_session(**params)
    except stripe.StripeError as exc:
        purchase.status = "failed"
        db.commit()
        logger.exception("stripe_single_job_checkout_failed", job_id=str(job.id))
        raise HTTPException(status_code=502, detail="Could not start single-job checkout") from exc
    purchase.stripe_checkout_session_id = checkout_session.id
    db.commit()
    if not checkout_session.url:
        raise HTTPException(status_code=502, detail="Stripe did not return a checkout URL")
    return {"url": checkout_session.url, "session_id": checkout_session.id}


@router.post("/portal", dependencies=[Depends(require_csrf)])
def create_portal_session(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, str]:
    settings = _stripe_settings()
    user = _user_from_cookie(db, raw_session)
    if not user.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No billing account was found")
    try:
        portal = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{settings.app_base_url.rstrip('/')}/account/billing",
        )
    except stripe.StripeError as exc:
        logger.exception("stripe_portal_creation_failed", user_id=str(user.id))
        raise HTTPException(status_code=502, detail="Could not open billing management") from exc
    return {"url": portal.url}


@router.get("/status")
def billing_status(
    db: Db,
    raw_session: Annotated[str | None, Cookie(alias="rc_session")] = None,
) -> dict[str, object]:
    user = _user_from_cookie(db, raw_session)
    subscription = db.scalar(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.current_period_end.desc())
        .limit(1)
    )
    day_pass = db.scalar(
        select(DayPass)
        .where(DayPass.user_id == user.id, DayPass.ends_at > datetime.now(UTC))
        .order_by(DayPass.ends_at.desc())
        .limit(1)
    )
    account = db.get(CreditAccount, user.id)
    return {
        "level": user_level(db, user).name.lower(),
        "credits": max(0, (account.balance - account.held) if account else 0),
        "subscription": (
            {
                "status": subscription.status,
                "current_period_end": (
                    subscription.current_period_end.isoformat()
                    if subscription.current_period_end
                    else None
                ),
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }
            if subscription
            else None
        ),
        "day_pass_ends_at": day_pass.ends_at.isoformat() if day_pass else None,
    }


def _object_id(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        raw_id = value.get("id")
        return raw_id if isinstance(raw_id, str) else None
    return None


def _from_timestamp(value: object) -> datetime | None:
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, UTC)
    return None


def _customer_user(db: Session, customer_id: str | None) -> User | None:
    if not customer_id:
        return None
    return db.scalar(select(User).where(User.stripe_customer_id == customer_id))


def _grant_credits(
    db: Session,
    user: User,
    amount: int,
    *,
    kind: str,
    reference_id: str,
    expires_at: datetime | None,
    note: str,
) -> None:
    if db.scalar(select(CreditLedger.id).where(CreditLedger.reference_id == reference_id)):
        return
    account = db.get(CreditAccount, user.id, with_for_update=True)
    if account is None:
        account = CreditAccount(user_id=user.id, balance=0, held=0)
        db.add(account)
        db.flush()
    account.balance += amount
    ledger_id = uuid4()
    db.add(
        CreditLedger(
            id=ledger_id,
            user_id=user.id,
            amount=amount,
            kind=kind,
            reference_id=reference_id,
            expires_at=expires_at,
            note=note[:255],
        )
    )
    db.add(
        CreditLot(
            user_id=user.id,
            source_ledger_id=ledger_id,
            total=amount,
            remaining=amount,
            held=0,
            expires_at=expires_at,
        )
    )


def _process_checkout(db: Session, obj: dict[str, object]) -> tuple[str, str] | None:
    metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    purchase_id = metadata.get("rendercart_purchase_id") if isinstance(metadata, dict) else None
    if not isinstance(purchase_id, str):
        return None
    purchase = db.get(Purchase, UUID(purchase_id))
    if purchase is None or purchase.status in {"paid", "refunded", "disputed"}:
        return None
    if obj.get("mode") == "subscription":
        customer_id = _object_id(obj.get("customer"))
        if customer_id and purchase.user_id:
            user = db.get(User, purchase.user_id)
            if user:
                user.stripe_customer_id = customer_id
        purchase.status = (
            "paid" if obj.get("payment_status") in {"paid", "no_payment_required"} else "pending"
        )
        return None
    if obj.get("payment_status") not in {"paid", "no_payment_required"}:
        return None
    if obj.get("currency") != "usd" or obj.get("amount_subtotal") != purchase.amount_cents:
        raise ValueError("Checkout amount or currency does not match the internal purchase")
    checkout_session_id = obj.get("id")
    if not isinstance(checkout_session_id, str):
        raise ValueError("Checkout session has no ID")
    purchase.stripe_checkout_session_id = checkout_session_id
    purchase.stripe_payment_intent_id = _object_id(obj.get("payment_intent"))
    purchase.status = "paid"
    magic_link: tuple[str, str] | None = None
    if purchase.kind == "day_pass":
        if not purchase.user_id and purchase.email:
            user = db.scalar(select(User).where(User.email == purchase.email.casefold()))
            if user is None:
                user = User(email=purchase.email.casefold())
                db.add(user)
                db.flush()
            if user.is_banned:
                raise ValueError("The day-pass email belongs to an unavailable account")
            purchase.user_id = user.id
            purchase.guest_id = None
            customer_id = _object_id(obj.get("customer"))
            if customer_id:
                user.stripe_customer_id = customer_id
            magic_link = (
                user.email,
                auth_service.create_auth_token(db, user, TokenPurpose.MAGIC_LINK),
            )
        if not purchase.user_id:
            raise ValueError("Day pass purchase is missing an account email")
        payment_id = purchase.stripe_payment_intent_id
        if not payment_id:
            raise ValueError("Paid day pass has no payment intent")
        if db.scalar(select(DayPass.id).where(DayPass.stripe_payment_intent_id == payment_id)):
            return magic_link
        now = datetime.now(UTC)
        ends_at = now + timedelta(hours=24)
        db.add(
            DayPass(
                user_id=purchase.user_id,
                email=purchase.email,
                stripe_payment_intent_id=payment_id,
                starts_at=now,
                ends_at=ends_at,
            )
        )
        user = db.get(User, purchase.user_id)
        if user and purchase.credits_granted:
            _grant_credits(
                db,
                user,
                purchase.credits_granted,
                kind="grant_daypass",
                reference_id=f"day-pass:{payment_id}:credits",
                expires_at=ends_at,
                note="Day pass credits",
            )
    elif purchase.kind == "single_job":
        if not purchase.job_id:
            raise ValueError("Single-job purchase has no job reference")
        job = db.get(Job, purchase.job_id, with_for_update=True)
        if job is None:
            raise ValueError("Paid single-job purchase references a missing job")
        if job.payment_tier != purchase.product_key:
            raise ValueError("Single-job purchase tier does not match the job")
        if job.state == JobState.SUCCEEDED and job.locked_output_key:
            if not job.locked_output_filename or not job.locked_output_content_type:
                raise ValueError("Locked preview result is incomplete")
            job.output_key = job.locked_output_key
            job.output_filename = job.locked_output_filename
            job.output_content_type = job.locked_output_content_type
            job.locked_output_key = None
            job.locked_output_filename = None
            job.locked_output_content_type = None
            job.expires_at = datetime.now(UTC) + timedelta(hours=24)
            db.add(
                AuditLog(
                    actor_user_id=job.user_id,
                    action="billing.preview_unlocked",
                    target=str(job.id),
                    details={"purchase_id": str(purchase.id)},
                )
            )
        elif job.state == JobState.AWAITING_PAYMENT:
            job.state = JobState.QUEUED
            job.expires_at = datetime.now(UTC) + timedelta(days=1)
            db.add(JobDispatch(job_id=job.id))
        elif job.state not in {JobState.QUEUED, JobState.RUNNING, JobState.SUCCEEDED}:
            db.add(
                AuditLog(
                    action="billing.paid_job_expired_before_fulfillment",
                    target=str(job.id),
                    details={"purchase_id": str(purchase.id)},
                )
            )
    elif purchase.kind == "credit_pack":
        if not purchase.user_id or not purchase.stripe_payment_intent_id:
            raise ValueError("Credit purchase is missing an account or payment intent")
        user = db.get(User, purchase.user_id)
        if user and purchase.credits_granted:
            _grant_credits(
                db,
                user,
                purchase.credits_granted,
                kind="purchase",
                reference_id=f"credit-pack:{purchase.stripe_payment_intent_id}:credits",
                expires_at=datetime.now(UTC) + timedelta(days=365),
                note=f"Purchased {purchase.product_key}",
            )
    return magic_link


def _upsert_subscription(db: Session, obj: dict[str, object]) -> None:
    subscription_id = obj.get("id")
    customer_id = _object_id(obj.get("customer"))
    if not isinstance(subscription_id, str) or not customer_id:
        return
    user_id = None
    metadata = obj.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("rendercart_user_id"), str):
        try:
            user_id = UUID(metadata["rendercart_user_id"])
        except ValueError:
            user_id = None
    user = db.get(User, user_id) if user_id else _customer_user(db, customer_id)
    if user is None:
        logger.warning("stripe_subscription_user_missing", subscription_id=subscription_id)
        return
    subscription = db.scalar(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    if subscription is None:
        subscription = Subscription(
            user_id=user.id,
            stripe_subscription_id=subscription_id,
            stripe_customer_id=customer_id,
            status=str(obj.get("status", "incomplete")),
        )
        db.add(subscription)
    subscription.user_id = user.id
    subscription.stripe_customer_id = customer_id
    subscription.status = str(obj.get("status", "incomplete"))
    subscription.cancel_at_period_end = bool(obj.get("cancel_at_period_end", False))
    subscription.current_period_start = _from_timestamp(obj.get("current_period_start"))
    subscription.current_period_end = _from_timestamp(obj.get("current_period_end"))
    items = obj.get("items")
    data = items.get("data") if isinstance(items, dict) else None
    if isinstance(data, list) and data and isinstance(data[0], dict):
        price = data[0].get("price")
        subscription.stripe_price_id = _object_id(price)


def _process_invoice_paid(db: Session, obj: dict[str, object], settings: Settings) -> None:
    billing_reason = obj.get("billing_reason")
    if billing_reason not in {"subscription_create", "subscription_cycle"}:
        return
    invoice_id = obj.get("id")
    user = _customer_user(db, _object_id(obj.get("customer")))
    if not isinstance(invoice_id, str) or user is None:
        return
    lines = obj.get("lines")
    line_data = lines.get("data") if isinstance(lines, dict) else None
    expiry = None
    if isinstance(line_data, list) and line_data and isinstance(line_data[0], dict):
        period = line_data[0].get("period")
        expiry = _from_timestamp(period.get("end")) if isinstance(period, dict) else None
    if expiry is None:
        subscription_id = _object_id(obj.get("subscription"))
        subscription = (
            db.scalar(
                select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
            )
            if subscription_id
            else None
        )
        expiry = subscription.current_period_end if subscription else None
    _grant_credits(
        db,
        user,
        settings.pro_monthly_credits,
        kind="grant_monthly",
        reference_id=f"invoice:{invoice_id}:pro-credits",
        expires_at=expiry,
        note=f"Pro credits for {invoice_id}",
    )


def _process_refund(db: Session, obj: dict[str, object], *, disputed: bool = False) -> None:
    payment_intent = _object_id(obj.get("payment_intent"))
    if not payment_intent:
        return
    purchase = db.scalar(
        select(Purchase).where(Purchase.stripe_payment_intent_id == payment_intent)
    )
    if purchase is None or purchase.status in {"refunded", "disputed"}:
        return
    purchase.status = "disputed" if disputed else "refunded"
    purchase.refunded_at = datetime.now(UTC)
    if purchase.kind == "day_pass":
        passes = list(
            db.scalars(select(DayPass).where(DayPass.stripe_payment_intent_id == payment_intent))
        )
        for day_pass in passes:
            day_pass.ends_at = min(day_pass.ends_at, datetime.now(UTC))
    if purchase.kind == "single_job" and purchase.job_id:
        job = db.get(Job, purchase.job_id)
        if job:
            job.state = JobState.CANCELLED
            job.error_code = "payment_refunded"
            job.finished_at = datetime.now(UTC)
    if purchase.user_id and purchase.credits_granted:
        source_reference = (
            f"day-pass:{payment_intent}:credits"
            if purchase.kind == "day_pass"
            else f"credit-pack:{payment_intent}:credits"
        )
        lot = db.scalar(
            select(CreditLot)
            .join(CreditLedger, CreditLot.source_ledger_id == CreditLedger.id)
            .where(CreditLedger.reference_id == source_reference)
            .with_for_update()
        )
        account = db.get(CreditAccount, purchase.user_id, with_for_update=True)
        if lot and account:
            amount = max(0, lot.remaining - lot.held)
            lot.remaining = lot.held
            lot.expires_at = datetime.now(UTC)
            debit = min(amount, max(0, account.balance - account.held))
            account.balance -= debit
            if debit:
                db.add(
                    CreditLedger(
                        user_id=purchase.user_id,
                        amount=-debit,
                        kind="refund",
                        reference_id=f"stripe-refund:{payment_intent}",
                        note="Credits revoked after payment refund or dispute",
                    )
                )
    db.add(
        AuditLog(
            action="billing.payment_disputed" if disputed else "billing.payment_refunded",
            target=str(purchase.id),
            details={"payment_intent_id": payment_intent},
        )
    )


def _process_event(
    db: Session, event: dict[str, object], settings: Settings
) -> tuple[str, str] | None:
    event_type = event.get("type")
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(event_type, str) or not isinstance(obj, dict):
        return None
    magic_link: tuple[str, str] | None = None
    if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        magic_link = _process_checkout(db, obj)
    elif event_type == "checkout.session.async_payment_failed":
        metadata = obj.get("metadata")
        purchase_id = metadata.get("rendercart_purchase_id") if isinstance(metadata, dict) else None
        if isinstance(purchase_id, str):
            purchase = db.get(Purchase, UUID(purchase_id))
            if purchase and purchase.status == "pending":
                purchase.status = "failed"
                if purchase.job_id:
                    job = db.get(Job, purchase.job_id)
                    if job and job.state == JobState.AWAITING_PAYMENT:
                        job.state = JobState.FAILED
                        job.error_code = "payment_failed"
                        job.finished_at = datetime.now(UTC)
    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        _upsert_subscription(db, obj)
    elif event_type == "invoice.paid":
        _process_invoice_paid(db, obj, settings)
    elif event_type == "invoice.payment_failed":
        user = _customer_user(db, _object_id(obj.get("customer")))
        if user:
            db.add(
                AuditLog(
                    action="billing.invoice_payment_failed",
                    target=str(user.id),
                    details={"invoice_id": str(obj.get("id", ""))},
                )
            )
    elif event_type == "charge.refunded":
        _process_refund(db, obj)
    elif event_type == "charge.dispute.created":
        _process_refund(db, obj, disputed=True)
    return magic_link


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Db,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, object]:
    settings = get_settings()
    if not settings.stripe_webhook_secret or not settings.stripe_webhook_secret.get_secret_value():
        raise HTTPException(status_code=503, detail="Stripe webhook signing is not configured")
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.stripe_webhook_secret.get_secret_value(),
        )
        event_data = cast(dict[str, object], event.to_dict_recursive())
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature") from exc

    event_id = event_data.get("id")
    event_type = event_data.get("type")
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        raise HTTPException(status_code=400, detail="Malformed Stripe event")
    if db.get(StripeEvent, event_id):
        return {"received": True, "duplicate": True}
    try:
        db.add(
            StripeEvent(
                event_id=event_id,
                event_type=event_type,
                payload_hash=hashlib.sha256(payload).hexdigest(),
            )
        )
        db.flush()
        magic_link = _process_event(db, event_data, settings)
        stripe_event = db.get(StripeEvent, event_id)
        if stripe_event:
            stripe_event.processed_at = datetime.now(UTC)
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(StripeEvent, event_id):
            return {"received": True, "duplicate": True}
        logger.exception("stripe_event_integrity_failure", event_id=event_id)
        raise HTTPException(status_code=500, detail="Could not process Stripe event") from None
    except Exception as exc:
        db.rollback()
        logger.exception("stripe_event_processing_failed", event_id=event_id, event_type=event_type)
        raise HTTPException(status_code=500, detail="Could not process Stripe event") from exc
    if magic_link:
        try:
            send_auth_link(magic_link[0], magic_link[1], "magic_link")
        except Exception:
            # Payment is committed; the purchaser can request another magic link.
            logger.exception(
                "guest_day_pass_magic_link_delivery_failed",
                email_hash=hashlib.sha256(magic_link[0].casefold().encode()).hexdigest(),
            )
    return {"received": True, "duplicate": False}
