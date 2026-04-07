import json
import os
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional in lean runtime environments
    def load_dotenv(*_args, **_kwargs):
        return False


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _get_list(name: str, default: List[str]) -> List[str]:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    trimmed = raw_value.strip()
    if trimmed.startswith("["):
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    return [value.strip() for value in trimmed.split(",") if value.strip()] or default


class Settings(BaseModel):
    environment: str = "development"
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "rendercart"
    postgres_user: str = "rendercart"
    postgres_password: str = "rendercart"
    database_url: str | None = None
    business_api_keys_config: str = str(PROJECT_ROOT / "api" / "business_keys.json")
    no_auth: bool = False
    cors_allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8000"]
    )
    r2_endpoint: str | None = None
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None
    hf_home: str = "/cache/huggingface"
    model_registry_path: str = "configs/model_registry.yaml"
    preset_registry_path: str = "configs/preset_registry.yaml"
    default_model_id: str = "realvisxl_v4"
    default_preset_id: str = "realvisxl_default"
    rate_limit_per_minute: int = 10
    default_page_size: int = 50
    max_page_size: int = 200
    request_timeout_seconds: int = 30
    callback_timeout_seconds: int = 10
    max_upload_bytes: int = 10 * 1024 * 1024
    max_batch_items: int = 20

    # Shopify Integration
    shopify_api_key: str | None = None
    shopify_api_secret: str | None = None
    shopify_app_scopes: List[str] = Field(
        default_factory=lambda: ["write_products", "read_products"]
    )
    shopify_api_version: str = "2024-01"
    shopify_encryption_key: str | None = None
    shopify_app_host: str | None = None  # e.g. https://rendercart.com

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("ENVIRONMENT", "development"),
        redis_host=os.getenv("REDIS_HOST", "redis"),
        redis_port=_get_int("REDIS_PORT", 6379),
        redis_password=os.getenv("REDIS_PASSWORD", ""),
        postgres_host=os.getenv("POSTGRES_HOST", "postgres"),
        postgres_port=_get_int("POSTGRES_PORT", 5432),
        postgres_db=os.getenv("POSTGRES_DB", "rendercart"),
        postgres_user=os.getenv("POSTGRES_USER", "rendercart"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "rendercart"),
        database_url=os.getenv("DATABASE_URL"),
        business_api_keys_config=os.getenv(
            "BUSINESS_API_KEYS_CONFIG", str(PROJECT_ROOT / "api" / "business_keys.json")
        ),
        no_auth=_get_bool("NO_AUTH", False),
        cors_allowed_origins=_get_list(
            "CORS_ALLOWED_ORIGINS",
            ["http://localhost:5173", "http://localhost:8000"],
        ),
        r2_endpoint=os.getenv("R2_ENDPOINT"),
        r2_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        r2_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        r2_bucket_name=os.getenv("R2_BUCKET_NAME"),
        hf_home=os.getenv("HF_HOME", "/cache/huggingface"),
        model_registry_path=os.getenv("MODEL_REGISTRY_PATH", "configs/model_registry.yaml"),
        preset_registry_path=os.getenv("PRESET_REGISTRY_PATH", "configs/preset_registry.yaml"),
        default_model_id=os.getenv("DEFAULT_MODEL_ID", "realvisxl_v4"),
        default_preset_id=os.getenv("DEFAULT_PRESET_ID", "realvisxl_default"),
        rate_limit_per_minute=_get_int("RATE_LIMIT_PER_MINUTE", 10),
        default_page_size=_get_int("DEFAULT_PAGE_SIZE", 50),
        max_page_size=_get_int("MAX_PAGE_SIZE", 200),
        request_timeout_seconds=_get_int("REQUEST_TIMEOUT_SECONDS", 30),
        callback_timeout_seconds=_get_int("CALLBACK_TIMEOUT_SECONDS", 10),
        max_upload_bytes=_get_int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
        max_batch_items=_get_int("MAX_BATCH_ITEMS", 20),
        
        shopify_api_key=os.getenv("SHOPIFY_API_KEY"),
        shopify_api_secret=os.getenv("SHOPIFY_API_SECRET"),
        shopify_app_scopes=_get_list("SHOPIFY_APP_SCOPES", ["write_products", "read_products"]),
        shopify_api_version=os.getenv("SHOPIFY_API_VERSION", "2024-01"),
        shopify_encryption_key=os.getenv("SHOPIFY_ENCRYPTION_KEY"),
        shopify_app_host=os.getenv("SHOPIFY_APP_HOST"),
    )


settings = load_settings()
