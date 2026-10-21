from functools import lru_cache
from typing import Any, cast

import boto3
from botocore.client import Config

from rendercart.core.config import get_settings


@lru_cache
def _client(public: bool = False) -> Any:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_public_endpoint if public else settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def presign_upload(key: str, content_type: str) -> str:
    settings = get_settings()
    return cast(
        str,
        _client(True).generate_presigned_url(
            "put_object",
            Params={"Bucket": settings.s3_bucket_uploads, "Key": key, "ContentType": content_type},
            ExpiresIn=settings.upload_url_ttl_seconds,
        ),
    )


def presign_download(key: str, filename: str) -> str:
    settings = get_settings()
    return cast(
        str,
        _client(True).generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.s3_bucket_results,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
            },
            ExpiresIn=settings.download_url_ttl_seconds,
        ),
    )


def download_upload(key: str, target: str) -> None:
    settings = get_settings()
    _client().download_file(settings.s3_bucket_uploads, key, target)


def upload_result(key: str, source: str, content_type: str) -> None:
    settings = get_settings()
    _client().upload_file(
        source,
        settings.s3_bucket_results,
        key,
        ExtraArgs={"ContentType": content_type},
    )


def put_vault_object(key: str, body: bytes) -> None:
    settings = get_settings()
    _client().put_object(
        Bucket=settings.s3_bucket_vault,
        Key=key,
        Body=body,
        ContentType="application/octet-stream",
    )


def get_vault_object(key: str) -> bytes:
    settings = get_settings()
    response = _client().get_object(Bucket=settings.s3_bucket_vault, Key=key)
    try:
        return cast(bytes, response["Body"].read())
    finally:
        response["Body"].close()


def delete_object(bucket: str, key: str) -> None:
    _client().delete_object(Bucket=bucket, Key=key)


def head_upload(key: str) -> dict[str, object]:
    settings = get_settings()
    return cast(
        dict[str, object], _client().head_object(Bucket=settings.s3_bucket_uploads, Key=key)
    )
