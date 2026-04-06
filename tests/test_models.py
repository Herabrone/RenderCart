import pytest
from api.models import (
    BatchGenerateRequest,
    BrandKitCreateRequest,
    BrandKitStyleSnapshot,
    BrandKitUpdateRequest,
    GenerateRequest,
)
from config import settings


def test_generate_request_limits_num_outputs():
    with pytest.raises(ValueError):
        GenerateRequest(image_url="https://example.com/image.png", prompt="test", num_outputs=5)


def test_batch_generate_request_enforces_max_items():
    too_many_items = [
        {"image_url": f"https://example.com/{index}.png"}
        for index in range(settings.max_batch_items + 1)
    ]
    with pytest.raises(ValueError):
        BatchGenerateRequest(items=too_many_items, prompt="batch")


def test_brand_kit_create_request_requires_all_fields():
    with pytest.raises(ValueError):
        BrandKitCreateRequest(
            name="Flagship",
            background="",
            lighting="soft window light",
            tone="clean and modern",
            framing="centered product shot",
        )


def test_brand_kit_update_request_rejects_empty_payload():
    with pytest.raises(ValueError):
        BrandKitUpdateRequest()


def test_brand_kit_snapshot_builds_brand_style():
    snapshot = BrandKitStyleSnapshot(
        name="Flagship",
        background="white sweep",
        lighting="soft daylight",
        tone="elevated minimal",
        framing="tight crop",
    )

    assert snapshot.to_brand_style() == (
        "background: white sweep, lighting: soft daylight, "
        "tone: elevated minimal, framing: tight crop"
    )


def test_generate_request_accepts_brand_kit_metadata():
    request = GenerateRequest(
        image_url="https://example.com/image.png",
        prompt="hero product image",
        brand_kit_id=7,
        brand_kit_snapshot={
            "name": "Flagship",
            "background": "white sweep",
            "lighting": "soft daylight",
            "tone": "elevated minimal",
            "framing": "tight crop",
        },
    )

    assert request.brand_kit_id == 7
    assert request.brand_kit_snapshot is not None
    assert request.brand_kit_snapshot.name == "Flagship"
