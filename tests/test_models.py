import pytest
from api.models import BatchGenerateRequest, GenerateRequest
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
