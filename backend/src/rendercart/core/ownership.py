from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from rendercart.auth.models import User
from rendercart.core.guest import decode_guest_id
from rendercart.jobs.models import Job, Upload


def attach_guest_data(db: Session, user: User, raw_guest_cookie: str | None) -> None:
    """Attach unexpired guest uploads and jobs from this browser to a signed-in user.

    The guest identifier is accepted only from the signed, time-limited cookie. Updating
    rows in one transaction prevents another browser from claiming the guest's history.
    The caller commits the changes together with the authentication transaction.
    """
    guest_id = decode_guest_id(raw_guest_cookie)
    if guest_id is None:
        return

    now = datetime.now(UTC)
    db.execute(
        update(Upload)
        .where(
            Upload.guest_id == guest_id,
            Upload.user_id.is_(None),
            Upload.expires_at > now,
        )
        .values(user_id=user.id, guest_id=None)
    )
    db.execute(
        update(Job)
        .where(
            Job.guest_id == guest_id,
            Job.user_id.is_(None),
            Job.expires_at > now,
        )
        .values(user_id=user.id, guest_id=None)
    )
