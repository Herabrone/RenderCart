from collections.abc import Iterable

from rendercart.core.access import Level
from rendercart.registry.models import ToolManifest


def build_registry(manifests: Iterable[ToolManifest]) -> dict[str, ToolManifest]:
    registry: dict[str, ToolManifest] = {}
    for manifest in manifests:
        if manifest.slug in registry:
            raise ValueError(f"duplicate tool slug: {manifest.slug}")
        if manifest.restricted and (manifest.min_level != Level.SUPER_ADMIN or not manifest.hidden):
            raise ValueError(
                f"restricted tool must be hidden and super_admin-only: {manifest.slug}"
            )
        registry[manifest.slug] = manifest
    return registry


def visible_tools(registry: dict[str, ToolManifest], level: Level) -> list[ToolManifest]:
    return [
        tool
        for tool in registry.values()
        if level >= tool.min_level and (not tool.restricted or level == Level.SUPER_ADMIN)
    ]


def load_builtin_registry() -> dict[str, ToolManifest]:
    from rendercart.tools.business.business_card.manifest import TOOL as business_card
    from rendercart.tools.business.invoice.manifest import TOOL as invoice_generator
    from rendercart.tools.business.resume.manifest import TOOL as resume_builder
    from rendercart.tools.image.background_remover.manifest import TOOL as background_remover
    from rendercart.tools.image.converter.manifest import TOOL as image_converter
    from rendercart.tools.media.audio_convert.manifest import TOOL as audio_converter
    from rendercart.tools.media.audio_denoise.manifest import TOOL as audio_noise_reduction
    from rendercart.tools.media.audio_extract.manifest import TOOL as audio_extractor
    from rendercart.tools.media.audio_trim.manifest import TOOL as audio_trimmer
    from rendercart.tools.media.subtitle_generator.manifest import TOOL as subtitle_generator
    from rendercart.tools.media.subtitle_translation.manifest import TOOL as subtitle_translation
    from rendercart.tools.media.text_to_speech.manifest import TOOL as text_to_speech
    from rendercart.tools.media.transcription.manifest import TOOL as transcription
    from rendercart.tools.media.video_compress.manifest import TOOL as video_compressor
    from rendercart.tools.media.video_convert.manifest import TOOL as video_converter
    from rendercart.tools.media.video_gif.manifest import TOOL as video_to_gif
    from rendercart.tools.media.video_merge.manifest import TOOL as video_merger
    from rendercart.tools.media.video_trim.manifest import TOOL as video_trimmer
    from rendercart.tools.pdf.compress.manifest import TOOL as compress_pdf
    from rendercart.tools.pdf.edit.manifest import TOOL as edit_pdf
    from rendercart.tools.pdf.esign.manifest import TOOL as esign_pdf
    from rendercart.tools.pdf.extract_pages.manifest import TOOL as extract_pdf_pages
    from rendercart.tools.pdf.from_images.manifest import TOOL as images_to_pdf
    from rendercart.tools.pdf.merge.manifest import TOOL as merge_pdf
    from rendercart.tools.pdf.ocr.manifest import TOOL as ocr_pdf
    from rendercart.tools.pdf.office_to_pdf.manifest import TOOL as office_to_pdf
    from rendercart.tools.pdf.organize.manifest import TOOL as organize_pdf
    from rendercart.tools.pdf.protect.manifest import TOOL as protect_pdf
    from rendercart.tools.pdf.rotate.manifest import TOOL as rotate_pdf
    from rendercart.tools.pdf.split.manifest import TOOL as split_pdf
    from rendercart.tools.pdf.to_excel.manifest import TOOL as pdf_to_excel
    from rendercart.tools.pdf.to_images.manifest import TOOL as pdf_to_images
    from rendercart.tools.pdf.to_word.manifest import TOOL as pdf_to_word
    from rendercart.tools.vault.file_share.manifest import TOOL as vault_file_share
    from rendercart.tools.vault.pastebin.manifest import TOOL as vault_pastebin
    from rendercart.tools.vault.short_link.manifest import TOOL as vault_short_link
    from rendercart.tools.website_audit.manifest import TOOL as website_audit
    from rendercart.tools.writing.chat_pdf.manifest import TOOL as chat_with_pdf
    from rendercart.tools.writing.document_translation.manifest import TOOL as document_translator
    from rendercart.tools.writing.grammar.manifest import TOOL as grammar_fixer
    from rendercart.tools.writing.helper.manifest import TOOL as writing_helper
    from rendercart.tools.writing.paraphraser.manifest import TOOL as paraphraser
    from rendercart.tools.writing.summarizer.manifest import TOOL as summarizer

    return build_registry(
        [
            merge_pdf,
            ocr_pdf,
            organize_pdf,
            office_to_pdf,
            split_pdf,
            extract_pdf_pages,
            images_to_pdf,
            edit_pdf,
            esign_pdf,
            rotate_pdf,
            compress_pdf,
            protect_pdf,
            pdf_to_excel,
            pdf_to_images,
            pdf_to_word,
            image_converter,
            background_remover,
            audio_converter,
            audio_noise_reduction,
            audio_trimmer,
            audio_extractor,
            video_converter,
            video_compressor,
            video_trimmer,
            video_to_gif,
            video_merger,
            transcription,
            subtitle_generator,
            subtitle_translation,
            text_to_speech,
            summarizer,
            chat_with_pdf,
            document_translator,
            paraphraser,
            grammar_fixer,
            writing_helper,
            invoice_generator,
            resume_builder,
            business_card,
            vault_short_link,
            vault_pastebin,
            vault_file_share,
            website_audit,
        ]
    )
