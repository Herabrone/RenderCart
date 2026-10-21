from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Literal
from uuid import UUID
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from rendercart.registry.models import ToolOutput

_CURRENCIES = {"CAD", "USD", "EUR", "GBP", "AUD", "NZD", "JPY", "CHF", "INR"}
_CENT = Decimal("0.01")
_CURRENCY_SYMBOLS = {
    "CAD": "CA$",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "AUD": "A$",
    "NZD": "NZ$",
    "JPY": "¥",
    "CHF": "CHF ",
    "INR": "₹",
}


class InvoiceLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=240)
    quantity: Decimal = Field(gt=0, le=Decimal("1000000"))
    unit_price: Decimal = Field(ge=0, le=Decimal("100000000"))

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str) -> str:
        return value.strip()


class InvoicePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_type: Literal["invoice", "quote", "receipt"] = "invoice"
    number: str = Field(min_length=1, max_length=40)
    currency: str = Field(min_length=3, max_length=3)
    issued_on: date
    due_on: date | None = None
    business_name: str = Field(min_length=1, max_length=120)
    business_email: str | None = Field(default=None, max_length=320)
    business_address: str = Field(default="", max_length=500)
    client_name: str = Field(min_length=1, max_length=120)
    client_email: str | None = Field(default=None, max_length=320)
    client_address: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)
    tax_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    items: list[InvoiceLine] = Field(min_length=1, max_length=40)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("number", "business_name", "client_name", mode="before")
    @classmethod
    def trim_required(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_document(self) -> InvoicePayload:
        if self.currency not in _CURRENCIES:
            raise ValueError("unsupported_currency")
        if self.due_on and self.due_on < self.issued_on:
            raise ValueError("due_date_before_issue_date")
        if self.business_email and "@" not in self.business_email:
            raise ValueError("invalid_business_email")
        if self.client_email and "@" not in self.client_email:
            raise ValueError("invalid_client_email")
        return self


def _money(value: Decimal, currency: str) -> str:
    rounded = value.quantize(_CENT, rounding=ROUND_HALF_UP)
    digits = 0 if currency == "JPY" else 2
    rounded = rounded.quantize(Decimal("1") if digits == 0 else _CENT, rounding=ROUND_HALF_UP)
    return f"{_CURRENCY_SYMBOLS[currency]}{rounded:,.{digits}f} {currency}"


def _paragraph(value: str, style: ParagraphStyle) -> Paragraph:
    lines = "<br/>".join(escape(line) for line in value.splitlines())
    return Paragraph(lines, style)


def _rich_paragraph(markup: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(markup, style)


def _render(payload: InvoicePayload, output_path: Path, branded: bool) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#312e81"),
        alignment=0,
    )
    body = ParagraphStyle(
        "InvoiceBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=13
    )
    muted = ParagraphStyle("InvoiceMuted", parent=body, textColor=colors.HexColor("#475569"))
    right = ParagraphStyle("InvoiceRight", parent=body, alignment=TA_RIGHT)
    story: list[object] = []
    title = payload.document_type.capitalize()
    story.extend([_paragraph(payload.business_name, title_style), Spacer(1, 6)])
    business_contact = "\n".join(
        part for part in (payload.business_address, payload.business_email or "") if part
    )
    story.extend([_paragraph(business_contact or "", muted), Spacer(1, 24)])
    issue_detail = f"Issued {payload.issued_on.isoformat()}"
    if payload.due_on:
        issue_detail += f"<br/>Due {payload.due_on.isoformat()}"
    details = Table(
        [
            [
                _rich_paragraph(f"<b>Bill to</b><br/>{escape(payload.client_name)}", body),
                _rich_paragraph(
                    f"<b>{title} {escape(payload.number)}</b><br/>{issue_detail}",
                    right,
                ),
            ],
            [
                _paragraph(
                    "\n".join(
                        part
                        for part in (payload.client_address, payload.client_email or "")
                        if part
                    ),
                    muted,
                ),
                "",
            ],
        ],
        colWidths=[3.6 * inch, 3.1 * inch],
    )
    details.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([details, Spacer(1, 26)])

    rows: list[list[object]] = [
        [
            _paragraph("<b>Description</b>", body),
            _paragraph("<b>Qty</b>", right),
            _paragraph("<b>Unit price</b>", right),
            _paragraph("<b>Amount</b>", right),
        ]
    ]
    subtotal = Decimal("0")
    for item in payload.items:
        line_total = (item.quantity * item.unit_price).quantize(_CENT, rounding=ROUND_HALF_UP)
        subtotal += line_total
        rows.append(
            [
                _paragraph(item.description, body),
                _paragraph(f"{item.quantity.normalize():f}", right),
                _paragraph(_money(item.unit_price, payload.currency), right),
                _paragraph(_money(line_total, payload.currency), right),
            ]
        )
    table = Table(rows, colWidths=[3.55 * inch, 0.6 * inch, 1.25 * inch, 1.3 * inch], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#c7d2fe")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.extend([table, Spacer(1, 12)])
    tax = (subtotal * payload.tax_percent / Decimal("100")).quantize(_CENT, rounding=ROUND_HALF_UP)
    total = subtotal + tax
    totals = Table(
        [
            ["Subtotal", _money(subtotal, payload.currency)],
            [f"Tax ({payload.tax_percent.normalize():f}%)", _money(tax, payload.currency)],
            [
                _paragraph("<b>Total</b>", body),
                _paragraph(f"<b>{_money(total, payload.currency)}</b>", right),
            ],
        ],
        colWidths=[1.9 * inch, 1.3 * inch],
        hAlign="RIGHT",
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEABOVE", (0, 2), (-1, 2), 1, colors.HexColor("#64748b")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([totals, Spacer(1, 24)])
    if payload.notes.strip():
        story.extend(
            [_paragraph("<b>Notes</b>", body), Spacer(1, 4), _paragraph(payload.notes, muted)]
        )

    def draw_footer(canvas: object, _document: object) -> None:
        canvas.saveState()  # type: ignore[attr-defined]
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))  # type: ignore[attr-defined]
        canvas.line(0.75 * inch, 0.62 * inch, 7.75 * inch, 0.62 * inch)  # type: ignore[attr-defined]
        if branded:
            canvas.setFont("Helvetica", 7)  # type: ignore[attr-defined]
            canvas.setFillColor(colors.HexColor("#64748b"))  # type: ignore[attr-defined]
            canvas.drawCentredString(letter[0] / 2, 0.4 * inch, "Made with RenderCart")  # type: ignore[attr-defined]
        canvas.restoreState()  # type: ignore[attr-defined]

    document = BaseDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.85 * inch,
        title=f"{title} {payload.number}",
        author=payload.business_name,
    )
    document.addPageTemplates(
        [
            PageTemplate(
                id="invoice",
                frames=[
                    Frame(
                        0.75 * inch,
                        0.85 * inch,
                        letter[0] - 1.5 * inch,
                        letter[1] - 1.55 * inch,
                        id="invoice-frame",
                        showBoundary=0,
                    )
                ],
                onPage=draw_footer,
            )
        ]
    )
    document.build(story)


def run(
    input_paths: list[Path],
    output_dir: Path,
    invoice_json: str,
    branded: bool = True,
    progress: Callable[[int], None] | None = None,
    job_id: UUID | None = None,
) -> ToolOutput:
    del job_id
    if input_paths:
        raise ValueError("invoice_generator_does_not_accept_files")
    try:
        payload = InvoicePayload.model_validate_json(invoice_json)
    except (ValueError, InvalidOperation) as exc:
        raise ValueError("invalid_invoice_details") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_number = re.sub(r"[^A-Za-z0-9_-]", "-", payload.number)[:40].strip("-") or "document"
    output_path = output_dir / f"{payload.document_type}-{safe_number}.pdf"
    _render(payload, output_path, branded)
    if progress:
        progress(100)
    return ToolOutput(output_path, output_path.name, "application/pdf")
