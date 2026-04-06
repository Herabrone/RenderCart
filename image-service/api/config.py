try:
    from pydantic import Field
    from pydantic import BaseSettings
except ImportError:  # pydantic 2.12+ moved BaseSettings to pydantic-settings
    from pydantic import Field
    from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    environment: str = Field("development", env="ENVIRONMENT")
    redis_host: str = Field("redis", env="REDIS_HOST")
    redis_port: int = Field(6379, env="REDIS_PORT")
    redis_password: str = Field("", env="REDIS_PASSWORD")
    postgres_host: str = Field("postgres", env="POSTGRES_HOST")
    postgres_port: int = Field(5432, env="POSTGRES_PORT")
    postgres_db: str = Field("rendercart", env="POSTGRES_DB")
    postgres_user: str = Field("rendercart", env="POSTGRES_USER")
    postgres_password: str = Field("rendercart", env="POSTGRES_PASSWORD")
    database_url: str | None = Field(None, env="DATABASE_URL")
    business_api_keys_config: str = Field("api/business_keys.json", env="BUSINESS_API_KEYS_CONFIG")
    no_auth: bool = Field(False, env="NO_AUTH")
    r2_endpoint: str | None = Field(None, env="R2_ENDPOINT")
    r2_access_key_id: str | None = Field(None, env="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str | None = Field(None, env="R2_SECRET_ACCESS_KEY")
    r2_bucket_name: str | None = Field(None, env="R2_BUCKET_NAME")
    hf_home: str = Field("/cache/huggingface", env="HF_HOME")
    model_registry_path: str = Field("configs/model_registry.yaml", env="MODEL_REGISTRY_PATH")
    preset_registry_path: str = Field("configs/preset_registry.yaml", env="PRESET_REGISTRY_PATH")
    default_model_id: str = Field("realvisxl_v4", env="DEFAULT_MODEL_ID")
    default_preset_id: str = Field("realvisxl_default", env="DEFAULT_PRESET_ID")

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "allow",
    }

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
