import pytest
from pydantic import ValidationError

from rendercart.core.access import Level
from rendercart.registry.loader import build_registry, load_builtin_registry, visible_tools
from rendercart.registry.models import Category, Queue, Runtime, SeoMeta, ToolManifest


def manifest(**changes: object) -> ToolManifest:
    values: dict[str, object] = {
        "slug": "merge-pdf",
        "name": "Merge PDF",
        "category": Category.PDF,
        "summary": "Combine PDF files.",
        "runtime": Runtime.CPU,
        "queue": Queue.CPU_DEFAULT,
        "seo": SeoMeta(title="Merge PDFs", description="Combine documents."),
    }
    values.update(changes)
    return ToolManifest(**values)


def test_registry_rejects_duplicate_slugs() -> None:
    with pytest.raises(ValueError, match="duplicate tool slug"):
        build_registry([manifest(), manifest(name="Another merge")])


def test_restricted_tools_must_be_hidden_super_admin_only() -> None:
    with pytest.raises(ValidationError, match="restricted tools"):
        manifest(restricted=True)


def test_restricted_tools_are_hidden_from_non_super_admin() -> None:
    vault_tool = manifest(
        slug="url-shortener",
        restricted=True,
        hidden=True,
        min_level=Level.SUPER_ADMIN,
    )
    registry = build_registry([manifest(), vault_tool])

    assert [tool.slug for tool in visible_tools(registry, Level.FREE)] == ["merge-pdf"]
    assert {tool.slug for tool in visible_tools(registry, Level.SUPER_ADMIN)} == {
        "merge-pdf",
        "url-shortener",
    }


def test_gpu_tool_requires_gpu_queue_and_credit_cost() -> None:
    with pytest.raises(ValidationError, match="GPU tools must use a GPU queue"):
        manifest(runtime=Runtime.GPU, queue=Queue.CPU_DEFAULT, credit_cost=2)
    with pytest.raises(ValidationError, match="credit_cost"):
        manifest(runtime=Runtime.GPU, queue=Queue.GPU_IMAGE)


def test_builtin_registry_has_reference_tools() -> None:
    assert set(load_builtin_registry()) == {
        "merge-pdf",
        "image-converter",
        "extract-pdf-pages",
        "rotate-pdf",
        "pdf-to-excel",
        "compress-pdf",
        "protect-pdf",
        "pdf-to-images",
        "organize-pdf",
        "split-pdf",
        "background-remover",
        "pdf-ocr",
        "pdf-to-word",
        "image-to-pdf",
        "office-to-pdf",
        "edit-pdf",
        "audio-converter",
        "audio-trimmer",
        "audio-extractor",
        "video-converter",
        "video-compressor",
        "video-trimmer",
        "video-to-gif",
        "video-merger",
        "transcription",
        "subtitle-generator",
        "subtitle-translation",
        "text-to-speech",
        "esign-pdf",
        "audio-noise-reduction",
        "chat-with-pdf",
        "document-translator",
        "grammar-fixer",
        "invoice-generator",
        "business-card",
        "resume-builder",
        "summarizer",
        "paraphraser",
        "writing-helper",
        "url-shortener",
        "pastebin",
        "temp-file-share",
    }


def test_every_public_pdf_manifest_exposes_pro_batch_support() -> None:
    from rendercart.registry.models import Category

    pdf_tools = [
        tool
        for tool in load_builtin_registry().values()
        if tool.category == Category.PDF and tool.slug not in {"esign-pdf", "edit-pdf"}
    ]

    assert pdf_tools
    assert all(tool.batchable for tool in pdf_tools)
    assert all(tool.public_dict()["batch_max_files"] == 20 for tool in pdf_tools)


def test_preview_mode_is_server_controlled_and_hidden_from_tool_schema() -> None:
    registry = load_builtin_registry()
    details = registry["background-remover"].detail_dict()
    assert "preview" not in details["options_schema"]["properties"]


def test_ocr_page_limit_is_internal_and_not_client_configurable() -> None:
    tool = load_builtin_registry()["pdf-ocr"]
    details = tool.detail_dict()
    assert "max_pages" not in details["options_schema"]["properties"]
    assert tool.limits[Level.GUEST].max_pages == 1
    assert tool.limits[Level.FREE].max_pages == 3
    assert tool.credits_for_pages(0) == 0
    assert tool.credits_for_pages(1) == 1
    assert tool.credits_for_pages(10) == 1
    assert tool.credits_for_pages(11) == 2
    assert tool.credits_for_pages(200) == 20


def test_esign_personal_and_server_metadata_are_not_public_options() -> None:
    tool = load_builtin_registry()["esign-pdf"]
    schema = tool.detail_dict()["options_schema"]

    assert schema is not None
    assert not {"signer_name", "signer_email", "signer_ip", "signed_at"}.intersection(
        schema["properties"]
    )
    assert tool.options is not None
    assert tool.options.model_fields["signer_email"].json_schema_extra["sensitive"] is True


def test_video_credit_cost_uses_rounded_up_100_mib_units() -> None:
    tool = load_builtin_registry()["video-compressor"]
    unit = 100_000_000

    assert tool.credit_cost_per_100_mb == 1
    assert tool.credits_for_bytes(0) == 0
    assert tool.credits_for_bytes(unit) == 1
    assert tool.credits_for_bytes(unit + 1) == 2


