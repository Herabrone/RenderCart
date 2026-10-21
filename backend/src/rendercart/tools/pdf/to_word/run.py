from __future__ import annotations

from pathlib import Path
from typing import cast
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring
from zipfile import ZIP_DEFLATED, ZipFile

import pdfplumber

from rendercart.registry.models import ToolOutput
from rendercart.tools.pdf.extract_pages.run import _parse_pages

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
register_namespace("w", _W)
register_namespace("r", _R)


def _paragraph(text: str) -> Element:
    paragraph = Element(f"{{{_W}}}p")
    if text:
        run = SubElement(paragraph, f"{{{_W}}}r")
        value = SubElement(
            run, f"{{{_W}}}t", {"{http://www.w3.org/XML/1998/namespace}space": "preserve"}
        )
        # XmlElement text is escaped by the serializer, so PDF text remains XML-safe.
        value.text = "".join(char for char in text if char in "\t\n\r" or ord(char) >= 32)
    return paragraph


def _document_xml(pages: list[str]) -> bytes:
    document = Element(f"{{{_W}}}document")
    body = SubElement(document, f"{{{_W}}}body")
    wrote_paragraph = False
    for page_index, page_text in enumerate(pages):
        lines = page_text.splitlines()
        if page_index and wrote_paragraph:
            page_break = Element(f"{{{_W}}}p")
            run = SubElement(page_break, f"{{{_W}}}r")
            SubElement(run, f"{{{_W}}}br", {f"{{{_W}}}type": "page"})
            body.append(page_break)
        for line in lines:
            body.append(_paragraph(line))
            wrote_paragraph = True
    if not wrote_paragraph:
        body.append(_paragraph("No selectable text was found in this PDF."))
    section = SubElement(body, f"{{{_W}}}sectPr")
    SubElement(
        section,
        f"{{{_W}}}pgSz",
        {f"{{{_W}}}w": "12240", f"{{{_W}}}h": "15840"},
    )
    SubElement(
        section,
        f"{{{_W}}}pgMar",
        {
            f"{{{_W}}}top": "1440",
            f"{{{_W}}}right": "1440",
            f"{{{_W}}}bottom": "1440",
            f"{{{_W}}}left": "1440",
            f"{{{_W}}}header": "720",
            f"{{{_W}}}footer": "720",
            f"{{{_W}}}gutter": "0",
        },
    )
    return cast(bytes, tostring(document, encoding="utf-8", xml_declaration=True))


def _write_docx(path: Path, pages: list[str]) -> None:
    content_types = Element(f"{{{_CT}}}Types")
    SubElement(
        content_types,
        f"{{{_CT}}}Default",
        {
            "Extension": "rels",
            "ContentType": "application/vnd.openxmlformats-package.relationships+xml",
        },
    )
    SubElement(
        content_types,
        f"{{{_CT}}}Default",
        {"Extension": "xml", "ContentType": "application/xml"},
    )
    SubElement(
        content_types,
        f"{{{_CT}}}Override",
        {
            "PartName": "/word/document.xml",
            "ContentType": _DOCX_CONTENT_TYPE,
        },
    )
    relationships = Element(f"{{{_REL}}}Relationships")
    SubElement(
        relationships,
        f"{{{_REL}}}Relationship",
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "Target": "word/document.xml",
        },
    )
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml", tostring(content_types, encoding="utf-8", xml_declaration=True)
        )
        archive.writestr(
            "_rels/.rels", tostring(relationships, encoding="utf-8", xml_declaration=True)
        )
        archive.writestr("word/document.xml", _document_xml(pages))


def run(input_paths: list[Path], output_dir: Path, pages: str = "") -> ToolOutput:
    if len(input_paths) != 1:
        raise ValueError("PDF to Word accepts one input file")
    page_texts: list[str] = []
    with pdfplumber.open(input_paths[0]) as document:
        page_indexes = _parse_pages(pages, len(document.pages))
        if not page_indexes:
            raise ValueError("empty_page_selection")
        page_texts = [
            document.pages[index].extract_text(layout=True) or "" for index in page_indexes
        ]
    if not any(text.strip() for text in page_texts):
        raise ValueError("no_selectable_text_found")
    output_path = output_dir / "converted.docx"
    _write_docx(output_path, page_texts)
    return ToolOutput(
        output_path,
        output_path.name,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
