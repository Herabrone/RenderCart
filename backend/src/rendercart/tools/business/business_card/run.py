from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from rendercart.registry.models import ToolOutput

_BLEED = inch / 8
_TRIM_WIDTH = 3.5 * inch
_TRIM_HEIGHT = 2 * inch
_PAGE_WIDTH = _TRIM_WIDTH + 2 * _BLEED
_PAGE_HEIGHT = _TRIM_HEIGHT + 2 * _BLEED


class CardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    title: str = Field(default="", max_length=120)
    company: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=80)
    website: str = Field(default="", max_length=240)
    accent_color: str = Field(default="#4f46e5", pattern=r"^#[0-9A-Fa-f]{6}$")
    layout: Literal["classic"] = "classic"

    @field_validator("name", "title", "company", "email", "phone", "website")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()


def _fit(canvas: Canvas, text: str, max_width: float, start_size: float, font: str) -> float:
    size = start_size
    while size > 6 and stringWidth(text, font, size) > max_width:
        size -= 0.5
    return size


def _crop_marks(canvas: Canvas) -> None:
    margin = 3
    length = 6
    left, bottom = _BLEED, _BLEED
    right, top = left + _TRIM_WIDTH, bottom + _TRIM_HEIGHT
    canvas.setStrokeColor(colors.HexColor("#334155"))
    canvas.setLineWidth(0.4)
    for x, y, x_direction, y_direction in (
        (left, bottom, -1, -1),
        (right, bottom, 1, -1),
        (left, top, -1, 1),
        (right, top, 1, 1),
    ):
        canvas.line(x + x_direction * margin, y, x + x_direction * (margin + length), y)
        canvas.line(x, y + y_direction * margin, x, y + y_direction * (margin + length))


def _render(payload: CardPayload, path: Path, branded: bool) -> None:
    canvas = Canvas(str(path), pagesize=(_PAGE_WIDTH, _PAGE_HEIGHT), pageCompression=1)
    canvas.setTitle(f"Business card — {payload.name}")
    canvas.setAuthor(payload.name)
    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, _PAGE_WIDTH, _PAGE_HEIGHT, fill=1, stroke=0)

    trim_left = _BLEED
    trim_bottom = _BLEED
    safe_left = trim_left + 18
    safe_right = trim_left + _TRIM_WIDTH - 18
    accent = colors.HexColor(payload.accent_color)
    canvas.setFillColor(accent)
    canvas.rect(trim_left, trim_bottom, 7, _TRIM_HEIGHT, fill=1, stroke=0)

    text_x = safe_left + 10
    text_width = safe_right - text_x
    name_font = "Helvetica-Bold"
    name_size = _fit(canvas, payload.name, text_width, 17, name_font)
    canvas.setFillColor(colors.HexColor("#111827"))
    canvas.setFont(name_font, name_size)
    canvas.drawString(text_x, trim_bottom + _TRIM_HEIGHT - 38, payload.name)

    subtitle = " · ".join(part for part in (payload.title, payload.company) if part)
    if subtitle:
        subtitle_size = _fit(canvas, subtitle, text_width, 9, "Helvetica")
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.setFont("Helvetica", subtitle_size)
        canvas.drawString(text_x, trim_bottom + _TRIM_HEIGHT - 54, subtitle)

    contact_lines = [value for value in (payload.email, payload.phone, payload.website) if value]
    canvas.setFillColor(colors.HexColor("#334155"))
    canvas.setFont("Helvetica", 8)
    y = trim_bottom + 31
    for contact in contact_lines[:3]:
        size = _fit(canvas, contact, text_width, 8, "Helvetica")
        canvas.setFont("Helvetica", size)
        canvas.drawString(text_x, y, contact)
        y -= 11

    if branded:
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.setFont("Helvetica", 5.5)
        canvas.drawRightString(
            trim_left + _TRIM_WIDTH - 12,
            trim_bottom + 8,
            "Made with RenderCart",
        )
    _crop_marks(canvas)
    canvas.showPage()
    canvas.save()


def run(
    input_paths: list[Path],
    output_dir: Path,
    card_json: str,
    branded: bool = True,
    progress: Callable[[int], None] | None = None,
    job_id: UUID | None = None,
) -> ToolOutput:
    del job_id
    if input_paths:
        raise ValueError("business_card_does_not_accept_files")
    try:
        payload = CardPayload.model_validate_json(card_json)
    except ValueError as exc:
        raise ValueError("invalid_business_card_details") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_-]", "-", payload.name)[:48].strip("-") or "business-card"
    output_path = output_dir / f"business-card-{safe_name}.pdf"
    _render(payload, output_path, branded)
    if progress:
        progress(100)
    return ToolOutput(output_path, output_path.name, "application/pdf")
