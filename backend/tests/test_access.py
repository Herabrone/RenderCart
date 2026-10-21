from datetime import UTC, datetime, timedelta

import pytest

from rendercart.core.access import AccessSubject, Level, StaffRole, effective_level

NOW = datetime(2026, 10, 17, tzinfo=UTC)


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        (None, Level.GUEST),
        (AccessSubject(), Level.FREE),
        (
            AccessSubject(
                subscription_status="active",
                subscription_period_end=NOW + timedelta(days=1),
            ),
            Level.PRO,
        ),
        (
            AccessSubject(day_pass_ends_at=NOW + timedelta(hours=1)),
            Level.DAY_PASS,
        ),
        (AccessSubject(staff_role=StaffRole.ADMIN), Level.ADMIN),
        (AccessSubject(staff_role=StaffRole.SUPER_ADMIN), Level.SUPER_ADMIN),
        (
            AccessSubject(
                staff_role=StaffRole.ADMIN,
                subscription_status="canceled",
                subscription_period_end=NOW - timedelta(days=1),
            ),
            Level.ADMIN,
        ),
    ],
)
def test_effective_level(subject: AccessSubject | None, expected: Level) -> None:
    assert effective_level(subject, now=NOW) == expected


def test_expired_pro_subscription_does_not_grant_pro() -> None:
    subject = AccessSubject(
        subscription_status="active",
        subscription_period_end=NOW,
    )

    assert effective_level(subject, now=NOW) == Level.FREE
