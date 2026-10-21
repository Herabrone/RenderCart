from pathlib import Path
from re import compile as compile_regex

import pdfplumber
from openpyxl import Workbook

from rendercart.registry.models import ToolOutput
from rendercart.tools.pdf.extract_pages.run import _parse_pages

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_LEADING_SPACE = compile_regex(r"^\s*")


def _safe_cell(value: str | None) -> str:
    text = value or ""
    leading = _LEADING_SPACE.match(text)
    if leading and text[leading.end() :].startswith(_FORMULA_PREFIXES):
        return f"'{text}"
    return text


def run(input_paths: list[Path], output_dir: Path, pages: str = "") -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("PDF table export accepts one input file")
    output_path = output_dir / "tables.xlsx"
    table_count = 0
    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:
        raise ValueError("workbook_creation_failed")
    sheet.title = "Extracted tables"
    with pdfplumber.open(input_paths[0]) as document:
        selected_pages = _parse_pages(pages, len(document.pages))
        for page_index in selected_pages:
            for table in document.pages[page_index].extract_tables():
                if not table:
                    continue
                if table_count:
                    sheet.append([])
                for row in table:
                    sheet.append([_safe_cell(cell) for cell in row])
                table_count += 1
    if table_count == 0:
        raise ValueError("no_tables_found")
    workbook.save(output_path)
    return ToolOutput(
        output_path,
        output_path.name,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
