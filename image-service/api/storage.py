import boto3
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class R2Storage:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            endpoint_url=os.getenv('R2_ENDPOINT'),
            aws_access_key_id=os.getenv('R2_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('R2_SECRET_ACCESS_KEY'),
        )
        self.bucket_name = os.getenv('R2_BUCKET_NAME', 'rendercart-images')

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
