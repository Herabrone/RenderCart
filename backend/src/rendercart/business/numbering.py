from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from rendercart.business.models import InvoiceNumberSequence


def reserve_number(db: Session, user_id: UUID, document_type: str) -> str:
    statement = (
        insert(InvoiceNumberSequence)
        .values(user_id=user_id, document_type=document_type, next_value=1)
        .on_conflict_do_update(
            constraint="uq_invoice_number_owner_type",
            set_={"next_value": InvoiceNumberSequence.next_value + 1},
        )
        .returning(InvoiceNumberSequence.next_value)
    )
    number = db.scalar(statement)
    if number is None:
        raise RuntimeError("invoice_number_reservation_failed")
    prefix = {"invoice": "INV", "quote": "QUO", "receipt": "REC"}[document_type]
    return f"{prefix}-{number:04d}"
