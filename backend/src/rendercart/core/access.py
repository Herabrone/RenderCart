from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum, StrEnum


class Level(IntEnum):
    GUEST = 0
    FREE = 1
    DAY_PASS = 2
    PRO = 3
    ADMIN = 4
    SUPER_ADMIN = 5


class StaffRole(StrEnum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


@dataclass(frozen=True)
class AccessSubject:
    staff_role: StaffRole = StaffRole.USER
    subscription_status: str | None = None
    subscription_period_end: datetime | None = None
    day_pass_ends_at: datetime | None = None


def effective_level(subject: AccessSubject | None, now: datetime | None = None) -> Level:
    """Compute a caller's plan/staff access level in one authoritative place."""
    if subject is None:
        return Level.GUEST

    current = now or datetime.now(UTC)
    plan = Level.FREE
    if (
        subject.subscription_status in {"active", "trialing", "past_due"}
        and subject.subscription_period_end is not None
        and subject.subscription_period_end > current
    ):
        plan = Level.PRO
    elif subject.day_pass_ends_at is not None and subject.day_pass_ends_at > current:
        plan = Level.DAY_PASS

    staff = {
        StaffRole.USER: Level.FREE,
        StaffRole.ADMIN: Level.ADMIN,
        StaffRole.SUPER_ADMIN: Level.SUPER_ADMIN,
    }[subject.staff_role]
    return max(plan, staff)
