from functools import cached_property
from typing import Dict

from config import settings


class R2Storage:
    def __init__(self):
        self.endpoint = settings.r2_endpoint
        self.access_key = settings.r2_access_key_id
        self.secret_key = settings.r2_secret_access_key
        self.bucket_name = settings.r2_bucket_name or "rendercart-images"

    @property
    def configured(self) -> bool:
        return all([self.endpoint, self.access_key, self.secret_key, self.bucket_name])

    def _ensure_configured(self) -> None:
        if not self.configured:
            raise RuntimeError("R2 storage is not configured")

    @cached_property
    def s3(self):
        self._ensure_configured()
        import boto3
        from botocore.client import Config

        return boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def generate_presigned_url(self, path: str, expires_in: int = 3600) -> str:
        key = path.lstrip("/")
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": key},
            ExpiresIn=expires_in,
        )

    def upload_image(self, image_bytes: bytes, path: str, content_type: str = "image/png") -> str:
        upload_result = self.upload_bytes(image_bytes, path, content_type=content_type)
        return upload_result["url"]

    def upload_bytes(self, payload: bytes, path: str, content_type: str) -> Dict[str, str]:
        key = path.lstrip("/")
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=payload,
            ContentType=content_type,
        )
        return {
            "storage_key": key,
            "url": self.generate_presigned_url(key),
        }

    def download_bytes(self, storage_key: str) -> bytes:
        response = self.s3.get_object(Bucket=self.bucket_name, Key=storage_key.lstrip("/"))
        return response["Body"].read()
