from api.ids import generate_batch_id, generate_job_id


def test_generated_job_id_uses_uuid_suffix():
    job_id = generate_job_id("business_1")
    assert job_id.startswith("job_business_1_")
    assert len(job_id.split("_")[-1]) == 32


def test_generated_batch_id_sanitizes_business_id():
    batch_id = generate_batch_id("acme corp")
    assert batch_id.startswith("batch_acme_corp_")
