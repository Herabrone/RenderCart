from __future__ import annotations

import html
import json
import os
import re
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit, urlunsplit
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from rendercart.registry.models import ToolOutput
from rendercart.safety.fetch import validate_public_http_url

_CATEGORY_LABELS = {
    "performance": "Performance",
    "accessibility": "Accessibility",
    "best-practices": "Best Practices",
    "seo": "SEO",
}
_METRIC_IDS = (
    "first-contentful-paint",
    "largest-contentful-paint",
    "speed-index",
    "total-blocking-time",
    "cumulative-layout-shift",
    "interaction-to-next-paint",
)


def _plain(value: object, maximum: int = 500) -> str:
    text = str(value)
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = html.unescape(text)
    return " ".join(text.split())[:maximum]


def _extract_report(
    payload: dict[str, object],
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    categories = payload.get("categories")
    audits = payload.get("audits")
    if not isinstance(categories, dict) or not isinstance(audits, dict):
        raise ValueError("lighthouse_report_invalid")
    scores: dict[str, object] = {}
    for key in _CATEGORY_LABELS:
        category = categories.get(key)
        score = category.get("score") if isinstance(category, dict) else None
        scores[key] = round(score * 100) if isinstance(score, int | float) else None

    metrics: dict[str, object] = {}
    for audit_id in _METRIC_IDS:
        audit = audits.get(audit_id)
        if isinstance(audit, dict):
            value = audit.get("displayValue")
            if isinstance(value, str) and value:
                metrics[audit_id] = _plain(value, 120)

    findings: list[dict[str, object]] = []
    for audit_id, audit in audits.items():
        if not isinstance(audit, dict) or audit.get("scoreDisplayMode") != "numeric":
            continue
        score = audit.get("score")
        if not isinstance(score, int | float) or score >= 0.9:
            continue
        details = audit.get("details")
        overall_savings_ms: object = 0
        if isinstance(details, dict):
            overall_savings_ms = details.get("overallSavingsMs", 0)
        savings_ms = 0
        if isinstance(overall_savings_ms, (int, float)):
            savings_ms = int(overall_savings_ms)
        findings.append(
            {
                "id": str(audit_id),
                "title": _plain(audit.get("title", audit_id), 160),
                "display_value": _plain(audit.get("displayValue", ""), 120),
                "description": _plain(audit.get("description", ""), 420),
                "score": round(score * 100),
                "savings_ms": savings_ms,
            }
        )
    findings.sort(key=lambda item: cast(int, item["savings_ms"]), reverse=True)
    return scores, metrics, findings[:20]


def _build_pdf(
    output_path: Path,
    *,
    url: str,
    device: str,
    scores: dict[str, object],
    metrics: dict[str, object],
    findings: list[dict[str, object]],
) -> None:
    parsed_url = urlsplit(url)
    display_url = urlunsplit(
        (parsed_url.scheme, parsed_url.netloc, parsed_url.path, "…" if parsed_url.query else "", "")
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AuditTitle",
        parent=styles["Title"],
        fontSize=22,
        leading=27,
        textColor=colors.HexColor("#33256f"),
    )
    heading_style = ParagraphStyle(
        "AuditHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#33256f"),
    )
    body_style = ParagraphStyle("AuditBody", parent=styles["BodyText"], fontSize=9, leading=13)
    small_style = ParagraphStyle("AuditSmall", parent=body_style, fontSize=8, leading=11)
    story: list[object] = [
        Paragraph("Website Speed & SEO Audit", title_style),
        Spacer(1, 0.12 * inch),
        Paragraph(f"<b>Website:</b> {escape(display_url)}", body_style),
        Paragraph(f"<b>Profile:</b> {escape(device.title())} · Lighthouse", body_style),
        Spacer(1, 0.22 * inch),
        Paragraph("Category scores", heading_style),
    ]
    score_rows = [["Category", "Score"]]
    for key, label in _CATEGORY_LABELS.items():
        score = scores.get(key)
        score_rows.append([label, f"{score}/100" if isinstance(score, int) else "N/A"])
    score_table = Table(score_rows, colWidths=[4.8 * inch, 1.2 * inch], repeatRows=1)
    score_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#33256f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8d5e5")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f4fa")]),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([score_table, Spacer(1, 0.22 * inch), Paragraph("Key metrics", heading_style)])
    metric_rows = [["Metric", "Result"]]
    metric_names = {
        "first-contentful-paint": "First Contentful Paint",
        "largest-contentful-paint": "Largest Contentful Paint",
        "speed-index": "Speed Index",
        "total-blocking-time": "Total Blocking Time",
        "cumulative-layout-shift": "Cumulative Layout Shift",
        "interaction-to-next-paint": "Interaction to Next Paint",
    }
    for key, label in metric_names.items():
        if key in metrics:
            metric_rows.append([label, str(metrics[key])])
    metrics_table = Table(metric_rows, colWidths=[4.8 * inch, 1.2 * inch], repeatRows=1)
    metrics_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#33256f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d8d5e5")),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    if len(metric_rows) > 1:
        story.append(metrics_table)
    else:
        story.append(Paragraph("No key metric values were reported.", body_style))
    story.extend([Spacer(1, 0.22 * inch), Paragraph("Prioritized recommendations", heading_style)])
    if not findings:
        story.append(
            Paragraph("Lighthouse reported no scored recommendations below 90/100.", body_style)
        )
    for finding in findings:
        title = escape(str(finding["title"]))
        details = escape(str(finding["description"]))
        value = escape(str(finding["display_value"]))
        summary = f"<b>{title}</b> · score {finding['score']}/100"
        if value:
            summary += f" · {value}"
        story.append(Paragraph(summary, body_style))
        if details:
            story.append(Paragraph(details, small_style))
        story.append(Spacer(1, 0.08 * inch))
    story.extend(
        [
            Spacer(1, 0.12 * inch),
            Paragraph(
                "Lighthouse results are a point-in-time lab measurement. Real-user performance "
                "can vary by network, device, location, and site content.",
                small_style,
            ),
        ]
    )
    SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="RenderCart Website Speed and SEO Audit",
        author="RenderCart",
    ).build(story)


def run(
    *,
    input_paths: list[Path],
    output_dir: Path,
    url: str,
    device: str = "mobile",
    progress: Callable[[int], None] | None = None,
) -> ToolOutput:
    if input_paths or device not in {"mobile", "desktop"}:
        raise ValueError("audit_options_invalid")
    scheme, host, port, _pinned_ip, _path = validate_public_http_url(url)
    if scheme != "https" or port != 443:
        raise ValueError("audit_requires_public_https")
    if progress:
        progress(5)
    report_path = output_dir / "lighthouse-report.json"
    chrome_flags = (
        "--headless=new --no-sandbox --disable-dev-shm-usage "
        "--proxy-server=http://egress-proxy:3128 --proxy-bypass-list=<-loopback>"
    )
    command = [
        "lighthouse",
        url,
        "--output=json",
        f"--output-path={report_path}",
        "--only-categories=performance,accessibility,best-practices,seo",
        f"--chrome-flags={chrome_flags}",
        "--quiet",
    ]
    if device == "desktop":
        command.append("--preset=desktop")
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}
    }
    environment["CHROME_PATH"] = "/usr/bin/chromium"
    if progress:
        progress(15)
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=output_dir,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        try:
            process.communicate(timeout=210)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("audit_timed_out") from exc
    except BaseException:
        try:
            kill_group = getattr(os, "killpg", None)
            if callable(kill_group):
                kill_group(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                kill_group = getattr(os, "killpg", None)
                if callable(kill_group):
                    kill_group(process.pid, getattr(signal, "SIGKILL", signal.SIGTERM))
                else:
                    process.kill()
            except OSError:
                process.kill()
            process.wait()
        raise
    if process.returncode != 0 or not report_path.is_file():
        raise ValueError("lighthouse_run_failed")
    if report_path.stat().st_size > 25_000_000:
        raise ValueError("lighthouse_report_too_large")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("lighthouse_report_invalid") from exc
    if not isinstance(report, dict):
        raise ValueError("lighthouse_report_invalid")
    scores, metrics, findings = _extract_report(report)
    output_path = output_dir / "website-audit.pdf"
    _build_pdf(
        output_path,
        url=url,
        device=device,
        scores=scores,
        metrics=metrics,
        findings=findings,
    )
    if progress:
        progress(100)
    elapsed_seconds = round(time.monotonic() - started)
    metadata: dict[str, object] = {
        "target_url": url,
        "host": host,
        "device": device,
        "scores": scores,
        "metrics": metrics,
        "findings": findings,
        "duration_seconds": elapsed_seconds,
    }
    return ToolOutput(
        path=output_path,
        filename="website-audit.pdf",
        content_type="application/pdf",
        metadata=metadata,
    )
