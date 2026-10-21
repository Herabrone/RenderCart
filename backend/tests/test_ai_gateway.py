from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import SecretStr

from rendercart.ai.gateway import AIError, AIGateway, ChatResult, _BudgetReservation
from rendercart.core.config import Settings


def _response(text: str = "answer") -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7},
    }


def test_mock_gateway_returns_deterministic_chat_and_embedding() -> None:
    recorded: list[tuple[ChatResult, str, object]] = []
    settings = Settings(ai_mode="mock")
    gateway = AIGateway(
        settings,
        usage_recorder=lambda result, task, job_id: recorded.append((result, task, job_id)),
    )

    result = gateway.chat([{"role": "user", "content": "Summarize this"}], task="summarize")
    vectors = gateway.embed(["same input", "same input"], task="test-embedding")

    assert result.content == "[mock:summarize] Summarize this"
    assert result.provider == "mock"
    assert vectors[0] == vectors[1]
    assert len(vectors[0]) == settings.ai_embedding_dimension
    assert [entry[1] for entry in recorded] == ["summarize", "test-embedding"]


def test_local_chat_uses_local_model_without_fallback() -> None:
    calls: list[tuple[str, dict[str, Any], str | None]] = []

    def transport(url: str, body: dict[str, Any], api_key: str | None) -> dict[str, Any]:
        calls.append((url, body, api_key))
        return _response("from local")

    settings = Settings(
        ai_mode="remote",
        ai_local_base_url="http://gpu.internal/v1",
        ai_local_api_key=SecretStr("gpu-secret"),
    )
    gateway = AIGateway(settings, transport=transport, usage_recorder=lambda *_args: None)

    result = gateway.chat([{"role": "user", "content": "hello"}], task="test")

    assert result.content == "from local"
    assert result.provider == "local"
    assert result.fallback_used is False
    assert calls[0][0] == "http://gpu.internal/v1/chat/completions"
    assert calls[0][2] == "gpu-secret"


def test_chat_falls_back_to_openrouter_after_local_failure() -> None:
    calls: list[str] = []

    def transport(url: str, _body: dict[str, Any], _key: str | None) -> dict[str, Any]:
        calls.append(url)
        if "gpu.internal" in url:
            raise AIError("local down")
        return _response("from fallback")

    settings = Settings(
        ai_mode="remote",
        ai_local_base_url="http://gpu.internal/v1",
        openrouter_api_key=SecretStr("router-secret"),
    )
    gateway = AIGateway(
        settings,
        transport=transport,
        budget_reserve=lambda amount, _settings: _BudgetReservation(date(2026, 10, 1), amount),
        budget_settle=lambda *_args: None,
        usage_recorder=lambda *_args: None,
    )

    result = gateway.chat([{"role": "user", "content": "hello"}], task="test", max_tokens=32)

    assert result.content == "from fallback"
    assert result.provider == "openrouter"
    assert result.fallback_used is True
    assert result.estimated_cost_usd > Decimal("0")
    assert len(calls) == 2


def test_openrouter_fallback_respects_monthly_spend_cap() -> None:
    def transport(_url: str, _body: dict[str, Any], _key: str | None) -> dict[str, Any]:
        raise AIError("local down")

    gateway = AIGateway(
        Settings(ai_mode="remote", openrouter_api_key=SecretStr("router-secret")),
        transport=transport,
        budget_reserve=lambda _estimate, _settings: None,
        usage_recorder=lambda *_args: None,
    )

    with pytest.raises(AIError, match="openrouter_spend_cap_reached"):
        gateway.chat([{"role": "user", "content": "hello"}], task="test")


def test_embeddings_never_use_openrouter_fallback() -> None:
    calls: list[str] = []

    def transport(url: str, _body: dict[str, Any], _key: str | None) -> dict[str, Any]:
        calls.append(url)
        raise AIError("local down")

    gateway = AIGateway(
        Settings(ai_mode="remote", openrouter_api_key=SecretStr("router-secret")),
        transport=transport,
        usage_recorder=lambda *_args: None,
    )

    with pytest.raises(AIError, match="local down"):
        gateway.embed(["document"])
    assert len(calls) == 1
    assert "embeddings" in calls[0]
