from pathlib import Path
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from rendercart.tools.business.resume import run as resume_run


@pytest.mark.parametrize("template", ["classic", "modern", "compact"])
def test_resume_templates_render_valid_pdf_with_the_same_user_content(
    tmp_path: Path, template: str
) -> None:
    output = resume_run.run(
        input_paths=[],
        output_dir=tmp_path / template,
        resume_json=(
            '{"name":"Avery Example","headline":"Product Designer",'
            '"summary":"Designs accessible tools.","experience":["Designer, Acme"],'
            '"education":[],"skills":["Research","Prototyping"]}'
        ),
        template=template,  # type: ignore[arg-type]
    )

    reader = PdfReader(output.path, strict=True)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert len(reader.pages) == 1
    assert "Avery Example" in text
    assert "Designs accessible tools." in text
    assert "Designer, Acme" in text
    assert "Research" in text


def test_resume_templates_have_distinct_layout_output(tmp_path: Path) -> None:
    resume_json = (
        '{"name":"Avery Example","summary":"Experienced product designer.",'
        '"experience":["Designer, Acme"],"education":[],"skills":[]}'
    )
    outputs = [
        resume_run.run(
            input_paths=[],
            output_dir=tmp_path / template,
            resume_json=resume_json,
            template=template,  # type: ignore[arg-type]
        )
        for template in ("classic", "modern", "compact")
    ]
    assert len({output.path.read_bytes() for output in outputs}) == 3


def test_resume_builder_rejects_unknown_template(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="invalid_resume_template"):
        resume_run.run(
            input_paths=[],
            output_dir=tmp_path,
            resume_json=(
                '{"name":"Avery Example","summary":"Experienced designer."}'
            ),
            template="executive",  # type: ignore[arg-type]
        )


def test_ai_resume_rewrite_only_replaces_requested_prose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def fake_chat(messages, *, task, max_tokens, job_id):
        captured.update(task=task, max_tokens=max_tokens, job_id=job_id, messages=messages)
        return SimpleNamespace(
            content=(
                '{"summary":"Clearer summary.","experience":["Improved description."],'
                '"cover_letter":"A more focused letter."}'
            )
        )

    monkeypatch.setattr(resume_run.gateway, "chat", fake_chat)
    output = resume_run.run(
        input_paths=[],
        output_dir=tmp_path,
        resume_json=(
            '{"name":"Avery Example","email":"avery@example.com",'
            '"summary":"Original summary.","experience":["Original description."],'
            '"education":["Original school"],"skills":["Original skill"],'
            '"cover_letter":"Original letter."}'
        ),
        rewrite_with_ai=True,
    )

    text = "\n".join(page.extract_text() or "" for page in PdfReader(output.path).pages)
    assert "Avery Example" in text
    assert "avery@example.com" in text
    assert "Clearer summary." in text
    assert "Improved description." in text
    assert "Original school" in text
    assert "Original skill" in text
    assert "A more focused letter." in text
    assert captured["task"] == "resume_rewrite"
    assert captured["max_tokens"] == 2_400
    assert "avery@example.com" not in str(captured["messages"])
