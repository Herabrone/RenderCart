import argparse
import sys
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import stripe
from sqlalchemy import select

from rendercart.auth.models import User
from rendercart.billing.models import Subscription
from rendercart.core.access import StaffRole
from rendercart.core.config import get_settings
from rendercart.core.db import SessionLocal
from rendercart.jobs.models import AuditLog, CreditAccount, CreditLedger, CreditLot

_STRIPE_CATALOG = {
    "pro_monthly": ("RenderCart Pro", "pro_monthly_amount_cents", 999, "month"),
    "day_pass": ("RenderCart Day Pass", "day_pass_amount_cents", 299, None),
    "job_s": ("RenderCart Single Job S", "job_s_amount_cents", 99, None),
    "job_m": ("RenderCart Single Job M", "job_m_amount_cents", 199, None),
    "job_l": ("RenderCart Single Job L", "job_l_amount_cents", 299, None),
    "credits_500": ("RenderCart 500 Credit Pack", "credits_500_amount_cents", 499, None),
    "credits_1500": ("RenderCart 1,500 Credit Pack", "credits_1500_amount_cents", 1199, None),
}


def _sync_stripe_products() -> None:
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise SystemExit("Set STRIPE_SECRET_KEY before syncing the Stripe catalog.")
    stripe.api_key = settings.stripe_secret_key.get_secret_value()
    product_list = cast(Any, stripe.Product.list(active=True, limit=100))
    price_list = cast(Any, stripe.Price.list(active=True, limit=100))
    products = list(product_list.auto_paging_iter())
    prices = list(price_list.auto_paging_iter())
    for key, (name, amount_setting, default_amount, interval) in _STRIPE_CATALOG.items():
        amount = int(getattr(settings, amount_setting, default_amount))
        product = next(
            (
                item
                for item in products
                if cast(dict[str, str], item.metadata).get("rendercart_key") == key
            ),
            None,
        )
        if product is None:
            product = stripe.Product.create(
                name=name,
                metadata={"rendercart_key": key},
                idempotency_key=f"rendercart-product-{key}-v1",
            )
            products.append(product)
        matching = next(
            (
                price
                for price in prices
                if price.product == product.id
                and price.unit_amount == amount
                and price.currency == "usd"
                and (
                    (interval is None and price.recurring is None)
                    or (price.recurring is not None and price.recurring.interval == interval)
                )
            ),
            None,
        )
        if matching is None:
            price_params: dict[str, object] = {
                "product": product.id,
                "unit_amount": amount,
                "currency": "usd",
                "metadata": {"rendercart_key": key},
                "idempotency_key": f"rendercart-price-{key}-{amount}-{interval or 'once'}-v1",
            }
            if interval:
                price_params["recurring"] = {"interval": interval}
            create_price = cast(Any, stripe.Price.create)
            matching = create_price(**price_params)
            prices.append(matching)
        print(f"STRIPE_PRICE_{key.upper()}={matching.id}")


def _comp_pro(email: str, days: int, reason: str) -> None:
    if days < 1 or days > 3650:
        raise SystemExit("--days must be between 1 and 3650.")
    normalized = email.strip().casefold()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == normalized))
        if user is None:
            raise SystemExit(f"No account found for {normalized}.")
        now = datetime.now(UTC)
        subscription = Subscription(
            user_id=user.id,
            stripe_subscription_id=f"comp_{uuid4().hex}",
            stripe_customer_id=user.stripe_customer_id or f"comp_{user.id}",
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=days),
            cancel_at_period_end=False,
        )
        db.add(subscription)
        db.add(
            AuditLog(
                action="billing.pro_comped",
                target=str(user.id),
                details={"days": days, "reason": reason[:255], "source": "cli"},
            )
        )
        db.commit()
    print(f"Granted Pro access to {normalized} for {days} days.")


def _refund_purchase(purchase_id: str, reason: str) -> None:
    from uuid import UUID

    from rendercart.billing.models import Purchase

    settings = get_settings()
    if not settings.stripe_secret_key:
        raise SystemExit("Set STRIPE_SECRET_KEY before issuing a refund.")
    stripe.api_key = settings.stripe_secret_key.get_secret_value()
    try:
        parsed_id = UUID(purchase_id)
    except ValueError as exc:
        raise SystemExit("Purchase ID must be a valid UUID.") from exc
    with SessionLocal() as db:
        purchase = db.get(Purchase, parsed_id)
        if purchase is None or purchase.status != "paid":
            raise SystemExit("Only paid purchases can be refunded.")
        if not purchase.stripe_payment_intent_id:
            raise SystemExit("This purchase has no refundable Stripe payment intent.")
        try:
            create_refund = cast(Any, stripe.Refund.create)
            refund = create_refund(
                payment_intent=purchase.stripe_payment_intent_id,
                reason="requested_by_customer",
                metadata={"rendercart_purchase_id": str(purchase.id), "reason": reason[:255]},
                idempotency_key=f"rendercart-refund-{purchase.id}",
            )
        except stripe.StripeError as exc:
            raise SystemExit(f"Stripe refund failed: {exc}") from exc
        db.add(
            AuditLog(
                action="billing.refund_requested",
                target=str(purchase.id),
                details={"refund_id": refund.id, "reason": reason[:255], "source": "cli"},
            )
        )
        db.commit()
    print(f"Refund {refund.id} requested. The verified webhook will revoke entitlement/credits.")


def _promote(email: str, role_name: str) -> None:
    role = StaffRole(role_name)
    normalized = email.strip().casefold()
    owner_email = get_settings().super_admin_email
    if role == StaffRole.SUPER_ADMIN and normalized != str(owner_email).casefold():
        raise SystemExit("Only SUPER_ADMIN_EMAIL can be the super admin.")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == normalized))
        if user is None:
            raise SystemExit(f"No account found for {normalized}; the user must sign up first.")
        if user.email_verified_at is None:
            raise SystemExit("The account must verify its email before receiving a staff role.")
        user.staff_role = role
        db.add(
            AuditLog(
                action="user.role_changed",
                target=str(user.id),
                details={"email": user.email, "role": role.value, "source": "cli"},
            )
        )
        db.commit()
    print(f"Set {normalized} role to {role.value}.")


def _grant_credits(email: str, amount: int, reason: str) -> None:
    if amount <= 0:
        raise SystemExit("Credit amount must be positive.")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().casefold()))
        if user is None:
            raise SystemExit(f"No account found for {email}.")
        account = db.get(CreditAccount, user.id, with_for_update=True)
        if account is None:
            account = CreditAccount(user_id=user.id, balance=0, held=0)
            db.add(account)
        account.balance += amount
        ledger_id = uuid4()
        db.add(
            CreditLedger(
                id=ledger_id,
                user_id=user.id,
                amount=amount,
                kind="grant",
                note=reason[:255],
            )
        )
        db.add(
            CreditLot(
                user_id=user.id,
                source_ledger_id=ledger_id,
                total=amount,
                remaining=amount,
                held=0,
            )
        )
        db.add(
            AuditLog(
                action="credits.granted",
                target=str(user.id),
                details={"amount": amount, "reason": reason, "source": "cli"},
            )
        )
        db.commit()
    print(f"Granted {amount} credits to {email.strip().casefold()}.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="rendercart")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("admin", help="staff account operations")
    admin_actions = admin.add_subparsers(dest="admin_action", required=True)
    promote = admin_actions.add_parser("promote")
    promote.add_argument("email")
    promote.add_argument(
        "--role", choices=[StaffRole.ADMIN.value, StaffRole.SUPER_ADMIN.value], default="admin"
    )
    credits = commands.add_parser("credits", help="credit ledger operations")
    credit_actions = credits.add_subparsers(dest="credit_action", required=True)
    grant = credit_actions.add_parser("grant")
    grant.add_argument("email")
    grant.add_argument("amount", type=int)
    grant.add_argument("--reason", required=True)
    billing = commands.add_parser("billing", help="billing administration")
    billing_actions = billing.add_subparsers(dest="billing_action", required=True)
    billing_actions.add_parser("sync-products", help="create/reuse Stripe products and prices")
    comp = billing_actions.add_parser("comp-pro", help="grant a logged, time-limited Pro comp")
    comp.add_argument("email")
    comp.add_argument("--days", type=int, default=30)
    comp.add_argument("--reason", required=True)
    refund = billing_actions.add_parser("refund", help="refund a paid purchase through Stripe")
    refund.add_argument("purchase_id")
    refund.add_argument("--reason", required=True)
    args = parser.parse_args()
    try:
        if args.command == "admin" and args.admin_action == "promote":
            _promote(args.email, args.role)
        elif args.command == "credits" and args.credit_action == "grant":
            _grant_credits(args.email, args.amount, args.reason)
        elif args.command == "billing" and args.billing_action == "sync-products":
            _sync_stripe_products()
        elif args.command == "billing" and args.billing_action == "comp-pro":
            _comp_pro(args.email, args.days, args.reason)
        elif args.command == "billing" and args.billing_action == "refund":
            _refund_purchase(args.purchase_id, args.reason)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
