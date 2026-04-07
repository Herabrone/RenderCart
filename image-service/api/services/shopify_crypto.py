import base64
from typing import Optional

from cryptography.fernet import Fernet
import structlog
from fastapi import HTTPException, status

from api.config import settings

logger = structlog.get_logger(__name__)

class ConfigurationError(Exception):
    """Raised when there's an issue with the application configuration."""
    pass


def _get_cipher() -> Fernet:
    """Gets the Fernet cipher instance based on the configured encryption key."""
    encryption_key = settings.shopify_encryption_key
    if not encryption_key:
        logger.error("shopify_encryption_key_missing")
        raise ConfigurationError("SHOPIFY_ENCRYPTION_KEY environment variable is not configured.")
    
    try:
        # Fernet expects a url-safe base64-encoded 32-byte key
        return Fernet(encryption_key.encode('utf-8'))
    except ValueError as e:
        logger.error("shopify_encryption_key_invalid", error=str(e))
        raise ConfigurationError("SHOPIFY_ENCRYPTION_KEY is invalid. Must be a URL-safe base64-encoded 32-byte key.")


def encrypt_token(plain_token: str) -> str:
    """Encrypts a Shopify access token."""
    try:
        cipher = _get_cipher()
        return cipher.encrypt(plain_token.encode('utf-8')).decode('utf-8')
    except ConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error("token_encryption_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to encrypt secure token."
        )


def decrypt_token(encrypted_token: str) -> str:
    """Decrypts a Shopify access token."""
    try:
        cipher = _get_cipher()
        return cipher.decrypt(encrypted_token.encode('utf-8')).decode('utf-8')
    except ConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error("token_decryption_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt secure token. The encryption key may have changed."
        )
