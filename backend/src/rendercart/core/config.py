from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[4] / ".env",
        extra="ignore",
    )

    app_env: str = "development"
    app_base_url: str = "http://localhost"
    secret_key: SecretStr = SecretStr("dev-only-change-this-to-a-random-secret")
    encryption_key: SecretStr = SecretStr("dev-only-change-this-to-a-random-32-byte-key")
    sentry_dsn: str | None = None
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://rendercart:rendercart@localhost:5432/rendercart"
    redis_url: str = "redis://localhost:6379/0"
    gpu_metrics_url: str | None = None
    s3_endpoint: str = "http://localhost:9000"
    s3_public_endpoint: str = "http://localhost:9000"
    s3_proxy_site: str = "http://storage.localhost"
    s3_access_key: str = "rendercart"
    s3_secret_key: SecretStr = SecretStr("rendercart-local-secret")
    s3_bucket_uploads: str = "uploads"
    s3_bucket_results: str = "results"
    s3_bucket_persistent: str = "persistent"
    s3_bucket_vault: str = "vault"
    upload_url_ttl_seconds: int = 900
    download_url_ttl_seconds: int = 300
    guest_cookie_name: str = "rc_guest"
    super_admin_email: str = "owner@example.com"
    turnstile_secret_key: SecretStr | None = None
    turnstile_site_key: str | None = None
    session_ttl_days: int = 30
    admin_session_ttl_hours: int = 12
    csrf_cookie_name: str = "rc_csrf"
    session_cookie_name: str = "rc_session"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    email_from: str = "RenderCart <noreply@example.local>"
    auth_token_ttl_minutes: int = 15
    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    github_client_id: str | None = None
    github_client_secret: SecretStr | None = None
    stripe_secret_key: SecretStr | None = None
    stripe_webhook_secret: SecretStr | None = None
    stripe_price_pro_monthly: str | None = None
    stripe_price_day_pass: str | None = None
    stripe_price_job_s: str | None = None
    stripe_price_job_m: str | None = None
    stripe_price_job_l: str | None = None
    stripe_price_credits_500: str | None = None
    stripe_price_credits_1500: str | None = None
    stripe_tax_enabled: bool = False
    pro_monthly_amount_cents: int = 999
    day_pass_amount_cents: int = 299
    job_s_amount_cents: int = 99
    job_m_amount_cents: int = 199
    job_l_amount_cents: int = 299
    credits_500_amount_cents: int = 499
    credits_1500_amount_cents: int = 1199
    pro_monthly_credits: int = 1000
    day_pass_credits: int = 150
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    ai_mode: Literal["mock", "local-cpu", "remote"] = "mock"
    ai_local_base_url: str = "http://localhost:8000/v1"
    ai_local_embedding_base_url: str = "http://localhost:8001/v1"
    ai_local_api_key: SecretStr | None = None
    ai_local_chat_model: str = "local-chat"
    ai_local_embedding_model: str = "BAAI/bge-m3"
    ai_embedding_dimension: int = 1024
    birefnet_model_id: str = "ZhengPeng7/BiRefNet"
    birefnet_model_revision: str = "e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4"
    transcription_model_id: str = "Systran/faster-whisper-large-v3"
    transcription_model_revision: str = "edaa852ec7e145841d8ffdb056a99866b5f0a478"
    diarization_model_id: str = "pyannote/speaker-diarization-community-1"
    diarization_model_revision: str = "3533c8cf8e369892e6b79ff1bf80f7b0286a54ee"
    diarization_hf_token: SecretStr | None = None
    tts_model_id: str = "hexgrad/Kokoro-82M"
    tts_model_revision: str = "c3327e9bac3dbe55779397bfa82de0f8806fb3bc"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: SecretStr | None = None
    openrouter_chat_model: str = "openai/gpt-4o-mini"
    openrouter_monthly_spend_cap_usd: float = 25.0
    openrouter_input_cost_per_million_usd: float = 0.15
    openrouter_output_cost_per_million_usd: float = 0.60
    google_web_risk_api_key: SecretStr | None = None
    dynamic_qr_trust_country_header: bool = False
    twilio_account_sid: str | None = None
    twilio_auth_token: SecretStr | None = None
    twilio_from_number: str | None = None
    monitor_sms_monthly_cap: int = 20

    @model_validator(mode="after")
    def require_production_secrets(self) -> "Settings":
        if self.ai_embedding_dimension != 1024:
            raise ValueError("AI_EMBEDDING_DIMENSION must be 1024 for the configured vector schema")
        if self.app_env == "production":
            if self.secret_key.get_secret_value() == "dev-only-change-this-to-a-random-secret":
                raise ValueError("SECRET_KEY must be changed for production")
            if (
                self.encryption_key.get_secret_value()
                == "dev-only-change-this-to-a-random-32-byte-key"
            ):
                raise ValueError("ENCRYPTION_KEY must be changed for production")
            if not self.turnstile_secret_key or not self.turnstile_site_key:
                raise ValueError("Turnstile site and secret keys are required in production")
            if self.super_admin_email == "owner@example.com":
                raise ValueError("SUPER_ADMIN_EMAIL must be set for production")
            app_url = urlsplit(self.app_base_url)
            if app_url.scheme != "https" or app_url.hostname in {"localhost", "127.0.0.1"}:
                raise ValueError("APP_BASE_URL must be a public HTTPS URL in production")
            s3_url = urlsplit(self.s3_public_endpoint)
            proxy_url = urlsplit(self.s3_proxy_site)
            if s3_url.scheme != "https" or s3_url.hostname in {"localhost", "127.0.0.1"}:
                raise ValueError("S3_PUBLIC_ENDPOINT must be reachable by production users")
            if proxy_url.scheme != "https" or self.s3_public_endpoint.rstrip(
                "/"
            ) != self.s3_proxy_site.rstrip("/"):
                raise ValueError("S3_PUBLIC_ENDPOINT must match the HTTPS S3_PROXY_SITE")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
