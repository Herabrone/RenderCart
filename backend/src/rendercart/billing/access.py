from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from rendercart.auth.models import User
from rendercart.billing.models import DayPass, Subscription
from rendercart.core.access import AccessSubject, Level, effective_level


def subject_for_user(db: Session, user: User, now: datetime | None = None) -> AccessSubject:
    current = now or datetime.now(UTC)
    subscription = db.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user.id,
            # Keep access during Stripe's retry/dunning window. Stripe's
            # subscription schedule ends access when it becomes canceled.
            Subscription.status.in_(["active", "trialing", "past_due"]),
            Subscription.current_period_end > current,
        )
        .order_by(Subscription.current_period_end.desc())
        .limit(1)
    )
    day_pass = db.scalar(
        select(DayPass)
        .where(
            DayPass.user_id == user.id,
            DayPass.starts_at <= current,
            DayPass.ends_at > current,
        )
        .order_by(DayPass.ends_at.desc())
        .limit(1)
    )
    return AccessSubject(
        staff_role=user.staff_role,
        subscription_status=subscription.status if subscription else None,
        subscription_period_end=subscription.current_period_end if subscription else None,
        day_pass_ends_at=day_pass.ends_at if day_pass else None,
    )


def user_level(db: Session, user: User, now: datetime | None = None) -> Level:
    return effective_level(subject_for_user(db, user, now), now)
