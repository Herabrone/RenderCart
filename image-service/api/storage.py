import boto3
from botocore.client import Config
from typing import Optional

from config import settings

class R2Storage:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(signature_version='s3v4'),
            region_name='auto',
        )
        self.bucket_name = settings.r2_bucket_name or 'rendercart-images'

    def upload_image(self, image_bytes: bytes, path: str) -> str:
        """
        Upload an image to R2 storage.
        
        Args:
            image_bytes: Raw image bytes
            path: Storage path in format /{business_id}/{job_id}/image_{n}.png
            
        Returns:
            Public URL of the uploaded image
        """
        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=path.lstrip('/'),
                Body=image_bytes,
                ContentType='image/png'
            )
            
            presigned_url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': path.lstrip('/')},
                ExpiresIn=3600,
            )
            return presigned_url
        except Exception as e:
            raise Exception(f"Failed to upload image to R2: {str(e)}")
