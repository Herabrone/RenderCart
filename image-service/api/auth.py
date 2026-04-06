import hashlib
import hmac
import json
from pathlib import Path

from config import settings
from fastapi import HTTPException, Request, Security, status
from fastapi.security.api_key import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyAuth:
    """API key authentication for business customers."""

    def __init__(self):
        self.business_keys = self._load_business_keys()

    def _load_business_keys(self) -> dict:
        config_path = Path(settings.business_api_keys_config)
        if not config_path.is_absolute():
            config_path = Path(__file__).resolve().parent / config_path
        if not config_path.exists():
            fallback_path = Path(__file__).resolve().parent / "business_keys.json"
            if fallback_path.exists():
                config_path = fallback_path
            else:
                return {}
        with config_path.open("r", encoding="utf-8") as file_handle:
            return json.load(file_handle)

    @staticmethod
    def get_api_key_hash(api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    @staticmethod
    def normalize_stored_hash(stored_hash: str) -> str:
        if not stored_hash:
            return ""
        if stored_hash.startswith("sha256:"):
            return stored_hash.split(":", 1)[1]
        return stored_hash

    def verify_api_key(self, api_key: str | None) -> str:
        if settings.no_auth:
            return "local_dev"

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API Key",
            )

        api_key_hash = self.get_api_key_hash(api_key)
        for business_id, config in self.business_keys.items():
            stored_hash = self.normalize_stored_hash(config.get("api_key_hash", ""))
            if stored_hash and hmac.compare_digest(stored_hash, api_key_hash):
                return business_id

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    async def verify_api_key_dependency(
        self,
        request: Request,
        api_key: str | None = Security(api_key_header),
    ) -> str:
        business_id = self.verify_api_key(api_key)
        request.state.business_id = business_id
        return business_id
