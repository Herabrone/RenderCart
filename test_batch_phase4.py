#!/usr/bin/env python3
"""
Phase 4 validation script for RenderCart batch feature hardening.
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'image-service'))


def test_batch_request_validation():
    from api.models import BatchGenerateRequest

    try:
        BatchGenerateRequest(items=[], prompt='Test prompt')
        raise AssertionError('BatchGenerateRequest should reject empty item lists')
    except ValueError:
        pass

    request = BatchGenerateRequest(
        items=[{'image_url': 'https://example.com/image.png'}],
        prompt='Test prompt',
    )
    assert len(request.items) == 1, 'BatchGenerateRequest should accept valid items'
    print('✓ BatchGenerateRequest validation works')


def test_batch_retry_request_defaults():
    from api.models import BatchRetryRequest

    request = BatchRetryRequest()
    assert request.keep_item_labels is True, 'BatchRetryRequest should default keep_item_labels to True'
    print('✓ BatchRetryRequest default values are correct')


def test_job_response_fields():
    from api.models import JobResponse

    response = JobResponse(
        job_id='job_test',
        status='pending',
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    required_fields = [
        'batch_id', 'item_index', 'item_label', 'input_file_name', 'original_image_url',
        'output_urls', 'result_urls', 'progress', 'step', 'error',
    ]

    for field in required_fields:
        assert hasattr(response, field), f'JobResponse missing field: {field}'

    print('✓ JobResponse contains required batch tracking fields')


def test_batch_response_fields():
    from api.models import BatchResponse, BatchItemSummary

    item = BatchItemSummary(
        item_index=0,
        label='Item A',
        job_id='job_test',
        status='completed',
        progress=100,
    )
    response = BatchResponse(
        batch_id='batch_test',
        business_id='business_1',
        status='completed',
        total_items=1,
        completed_items=1,
        failed_items=0,
        pending_items=0,
        progress=100,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        items=[item],
    )

    assert response.batch_id == 'batch_test', 'BatchResponse batch_id mismatch'
    assert len(response.items) == 1, 'BatchResponse items should include the item summary'
    print('✓ BatchResponse model validation works')


def main():
    print('Running Phase 4 validation tests...\n')
    test_batch_request_validation()
    test_batch_retry_request_defaults()
    test_job_response_fields()
    test_batch_response_fields()
    print('\nAll Phase 4 validation tests passed!')


if __name__ == '__main__':
    main()
