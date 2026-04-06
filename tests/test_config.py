from api.config import load_settings


def test_load_settings_respects_env(monkeypatch):
    monkeypatch.setenv("NO_AUTH", "true")
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "42")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000")

    settings = load_settings()

    assert settings.no_auth is True
    assert settings.rate_limit_per_minute == 42
    assert settings.cors_allowed_origins == ["http://localhost:5173", "http://localhost:8000"]
