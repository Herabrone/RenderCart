from enum import Enum
from typing import Any, Dict, Optional

from config import settings, resolve_preset_registry


class OutputFormat(str, Enum):
    PRODUCT_IMAGE = "product_image"
    PRODUCT_GALLERY = "product_gallery"
    COLLECTION_BANNER = "collection_banner"
    SALE_PROMO = "sale_promo"
    INSTAGRAM_AD = "instagram_ad"
    STORY_CREATIVE = "story_creative"
    SHOPIFY_STOREFRONT = "shopify_storefront"
    AMAZON_LISTING = "amazon_listing"
    SOCIAL_SQUARE = "social_square"
    SOCIAL_PORTRAIT = "social_portrait"


class GenerationMode(str, Enum):
    PREVIEW = "preview"
    PRODUCTION = "production"


class ProductCategory(str, Enum):
    GENERAL = "general"
    FASHION = "fashion"
    ELECTRONICS = "electronics"
    HOME = "home"
    BEAUTY = "beauty"
    FOOD = "food"
    JEWELRY = "jewelry"


class UseCase(str, Enum):
    MAIN_PRODUCT_IMAGE = "main_product_image"
    PRODUCT_GALLERY_IMAGE = "product_gallery_image"
    COLLECTION_BANNER = "collection_banner"
    SALE_PROMO = "sale_promo"
    INSTAGRAM_AD = "instagram_ad"
    STORY_CREATIVE = "story_creative"


OUTPUT_FORMAT_SPECS: Dict[OutputFormat, Dict[str, Any]] = {
    OutputFormat.PRODUCT_IMAGE: {
        "label": "Product image",
        "width": 1024,
        "height": 1024,
        "extension": "png",
    },
    OutputFormat.PRODUCT_GALLERY: {
        "label": "Product gallery image",
        "width": 1200,
        "height": 1200,
        "extension": "png",
    },
    OutputFormat.COLLECTION_BANNER: {
        "label": "Collection banner",
        "width": 1600,
        "height": 600,
        "extension": "jpg",
    },
    OutputFormat.SALE_PROMO: {
        "label": "Sale promo",
        "width": 1200,
        "height": 628,
        "extension": "jpg",
    },
    OutputFormat.INSTAGRAM_AD: {
        "label": "Instagram ad",
        "width": 1080,
        "height": 1080,
        "extension": "jpg",
    },
    OutputFormat.STORY_CREATIVE: {
        "label": "Story creative",
        "width": 1080,
        "height": 1920,
        "extension": "jpg",
    },
    OutputFormat.SHOPIFY_STOREFRONT: {
        "label": "Shopify storefront",
        "width": 1200,
        "height": 1200,
        "extension": "png",
    },
    OutputFormat.AMAZON_LISTING: {
        "label": "Amazon listing",
        "width": 1200,
        "height": 1200,
        "extension": "png",
    },
    OutputFormat.SOCIAL_SQUARE: {
        "label": "Social square",
        "width": 1080,
        "height": 1080,
        "extension": "jpg",
    },
    OutputFormat.SOCIAL_PORTRAIT: {
        "label": "Social portrait",
        "width": 1080,
        "height": 1920,
        "extension": "jpg",
    },
}


def _load_registry() -> Dict[str, Any]:
    try:
        registry = resolve_preset_registry()
        if not isinstance(registry, dict):
            return {}
        return registry
    except Exception:
        return {}


PRESET_REGISTRY = _load_registry()
DEFAULT_PRESET_ID = settings.default_preset_id or PRESET_REGISTRY.get("default_preset", "realvisxl_default")


def get_preset(preset_id: Optional[str] = None) -> Dict[str, Any]:
    if preset_id is None:
        preset_id = DEFAULT_PRESET_ID
    presets = PRESET_REGISTRY.get("presets", {})
    preset = presets.get(preset_id)
    if preset:
        return preset

    fallback = presets.get(DEFAULT_PRESET_ID)
    if fallback:
        return fallback

    raise ValueError(f"Unknown preset id: {preset_id}")


def build_prompt(
    user_prompt: str,
    preset_id: Optional[str] = None,
    use_case: Optional[Any] = None,
    product_category: Optional[Any] = None,
    brand_style: Optional[str] = None,
) -> str:
    preset = get_preset(preset_id)
    prompt_template = preset.get("prompt_template", "{user_prompt}")
    
    use_case_str = use_case.value if hasattr(use_case, 'value') else (use_case or "")
    product_category_str = product_category.value if hasattr(product_category, 'value') else (product_category or "")
    
    return prompt_template.format(
        user_prompt=user_prompt.strip(),
        use_case=use_case_str,
        product_category=product_category_str,
        brand_style=(brand_style or ""),
    ).strip()


def get_inference_params(preset_id: Optional[str] = None, mode: Optional[Any] = None) -> Dict[str, Any]:
    preset = get_preset(preset_id)
    inference_kwargs = dict(preset.get("inference_kwargs", {}))

    mode_str = mode.value if hasattr(mode, 'value') else (mode or GenerationMode.PRODUCTION.value)

    if mode_str == GenerationMode.PREVIEW.value:
        inference_kwargs["num_inference_steps"] = min(inference_kwargs.get("num_inference_steps", 20), 18)
        inference_kwargs["guidance_scale"] = min(inference_kwargs.get("guidance_scale", 7.0), 5.5)
        inference_kwargs["strength"] = min(inference_kwargs.get("strength", 0.7), 0.6)

    return inference_kwargs


def get_output_spec(output_format: Optional[str]) -> Dict[str, Any]:
    if not output_format:
        return OUTPUT_FORMAT_SPECS[OutputFormat.PRODUCT_IMAGE]
    try:
        format_enum = OutputFormat(output_format)
    except ValueError:
        return OUTPUT_FORMAT_SPECS[OutputFormat.PRODUCT_IMAGE]
    return OUTPUT_FORMAT_SPECS.get(format_enum, OUTPUT_FORMAT_SPECS[OutputFormat.PRODUCT_IMAGE])


def list_presets() -> Dict[str, Any]:
    return PRESET_REGISTRY.get("presets", {})


def list_output_formats() -> Dict[str, Any]:
    return {fmt.value: spec for fmt, spec in OUTPUT_FORMAT_SPECS.items()}
