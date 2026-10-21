import hashlib
import json
import math
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from rendercart.ai.models import AISpendWindow, AIUsage
from rendercart.core.config import Settings, get_settings
from rendercart.core.db import SessionLocal

logger = structlog.get_logger(__name__)


class AIError(RuntimeError):
    """Raised when the requested AI capability is unavailable."""


@dataclass(frozen=True)
class ChatResult:
    content: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal
    fallback_used: bool


@dataclass(frozen=True)
class _ProviderResult:
    payload: dict[str, Any]
    provider: str
    model: str


class _CircuitBreaker:
    def __init__(self, failures: int = 3, reset_seconds: float = 30.0) -> None:
        self.failures = failures
        self.reset_seconds = reset_seconds
        self.failure_count = 0
        self.opened_at: float | None = None

    def available(self, now: float) -> bool:
        if self.opened_at is None:
            return True
        if now - self.opened_at >= self.reset_seconds:
            self.opened_at = None
            self.failure_count = 0
            return True
        return False

    def success(self) -> None:
        self.failure_count = 0
        self.opened_at = None

    def failure(self, now: float) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failures:
            self.opened_at = now


def _post_json(url: str, body: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urlopen(request, timeout=90) as response:  # noqa: S310 - base URLs are operator config
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise AIError("provider_request_failed") from exc
    if not isinstance(result, dict):
        raise AIError("provider_returned_invalid_response")
    return result


def _usage_numbers(payload: dict[str, Any]) -> tuple[int, int]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return 0, 0
    return int(usage.get("prompt_tokens", 0)), int(usage.get("completion_tokens", 0))


@dataclass(frozen=True)
class _BudgetReservation:
    month_start: date
    amount: Decimal


def _reserve_openrouter_budget(
    estimated_cost: Decimal, settings: Settings
) -> _BudgetReservation | None:
    month_start = datetime.now(UTC).date().replace(day=1)
    cap = Decimal(str(settings.openrouter_monthly_spend_cap_usd))
    with SessionLocal() as db:
        with db.begin():
            db.execute(
                pg_insert(AISpendWindow)
                .values(month_start=month_start, reserved_usd=Decimal("0"))
                .on_conflict_do_nothing(index_elements=["month_start"])
            )
            window = db.scalar(
                select(AISpendWindow)
                .where(AISpendWindow.month_start == month_start)
                .with_for_update()
            )
            if window is None or window.reserved_usd + estimated_cost > cap:
                return None
            window.reserved_usd += estimated_cost
    return _BudgetReservation(month_start, estimated_cost)


def _settle_openrouter_budget(reservation: _BudgetReservation, actual_cost: Decimal) -> None:
    with SessionLocal() as db, db.begin():
        window = db.scalar(
            select(AISpendWindow)
            .where(AISpendWindow.month_start == reservation.month_start)
            .with_for_update()
        )
        if window is not None:
            window.reserved_usd = max(
                Decimal("0"), window.reserved_usd - reservation.amount + actual_cost
            )


def _default_usage_recorder(
    result: ChatResult, task: str, job_id: UUID | None, gpu_seconds: float = 0
) -> None:
    with SessionLocal() as db:
        db.add(
            AIUsage(
                job_id=job_id,
                provider=result.provider,
                model=result.model,
                task=task,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                gpu_seconds=gpu_seconds,
                estimated_cost_usd=result.estimated_cost_usd,
                fallback_used=result.fallback_used,
            )
        )
        db.commit()


class AIGateway:
    """Route model capabilities through the configured local-first provider policy."""

    def __init__(
        self,
        settings: Settings | None = None,
        transport: Callable[[str, dict[str, Any], str | None], dict[str, Any]] = _post_json,
        budget_reserve: Callable[
            [Decimal, Settings], _BudgetReservation | None
        ] = _reserve_openrouter_budget,
        budget_settle: Callable[[_BudgetReservation, Decimal], None] = _settle_openrouter_budget,
        usage_recorder: Callable[[ChatResult, str, UUID | None], None] = _default_usage_recorder,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport
        self.budget_reserve = budget_reserve
        self.budget_settle = budget_settle
        self.usage_recorder = usage_recorder
        self.clock = clock
        self.local_breaker = _CircuitBreaker()

    def _local_key(self) -> str | None:
        secret = self.settings.ai_local_api_key
        return secret.get_secret_value() if secret else None

    def _openrouter_key(self) -> str | None:
        secret = self.settings.openrouter_api_key
        return secret.get_secret_value() if secret else None

    def _mock_chat(self, messages: Sequence[dict[str, str]], task: str) -> ChatResult:
        last_user = next(
            (item["content"] for item in reversed(messages) if item["role"] == "user"), ""
        )
        content = f"[mock:{task}] {last_user[:300]}".strip()
        result = ChatResult(content, "mock", "canned", 0, 0, Decimal("0"), False)
        return result

    def _request(
        self,
        base_url: str,
        model: str,
        messages: Sequence[dict[str, str]],
        max_tokens: int,
        json_schema: dict[str, Any] | None,
        api_key: str | None,
    ) -> _ProviderResult:
        body: dict[str, Any] = {
            "model": model,
            "messages": list(messages),
            "max_tokens": max_tokens,
        }
        if json_schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "task_response", "strict": True, "schema": json_schema},
            }
        payload = self.transport(f"{base_url.rstrip('/')}/chat/completions", body, api_key)
        return _ProviderResult(payload, "local", model)

    def _openrouter_estimate(self, messages: Sequence[dict[str, str]], max_tokens: int) -> Decimal:
        input_tokens = sum(max(1, len(message.get("content", "")) // 4) for message in messages)
        input_cost = input_tokens * self.settings.openrouter_input_cost_per_million_usd / 1_000_000
        output_cost = max_tokens * self.settings.openrouter_output_cost_per_million_usd / 1_000_000
        return Decimal(str(input_cost + output_cost)).quantize(Decimal("0.000001"))

    def _parse_chat_result(self, response: _ProviderResult, fallback: bool) -> ChatResult:
        choices = response.payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise AIError("provider_returned_invalid_response")
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise AIError("provider_returned_invalid_response")
        prompt_tokens, completion_tokens = _usage_numbers(response.payload)
        cost = Decimal("0")
        if fallback:
            cost = (
                Decimal(prompt_tokens)
                * Decimal(str(self.settings.openrouter_input_cost_per_million_usd))
                + Decimal(completion_tokens)
                * Decimal(str(self.settings.openrouter_output_cost_per_million_usd))
            ) / Decimal(1_000_000)
        return ChatResult(
            content=message["content"],
            provider=response.provider,
            model=response.model,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            estimated_cost_usd=cost.quantize(Decimal("0.000001")),
            fallback_used=fallback,
        )

    def _record(self, result: ChatResult, task: str, job_id: UUID | None) -> ChatResult:
        self.usage_recorder(result, task, job_id)
        return result

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        task: str,
        max_tokens: int = 1024,
        json_schema: dict[str, Any] | None = None,
        priority: bool = False,
        job_id: UUID | None = None,
    ) -> ChatResult:
        del priority  # Priority is applied by Celery queue selection at job submission.
        if not messages or max_tokens < 1:
            raise ValueError("messages_and_positive_max_tokens_required")
        if self.settings.ai_mode == "mock":
            return self._record(self._mock_chat(messages, task), task, job_id)

        local_error: Exception | None = None
        if self.local_breaker.available(self.clock()):
            try:
                response = self._request(
                    self.settings.ai_local_base_url,
                    self.settings.ai_local_chat_model,
                    messages,
                    max_tokens,
                    json_schema,
                    self._local_key(),
                )
                self.local_breaker.success()
                return self._record(self._parse_chat_result(response, fallback=False), task, job_id)
            except Exception as exc:
                self.local_breaker.failure(self.clock())
                local_error = exc
                logger.warning("local_ai_provider_failed", task=task, error_type=type(exc).__name__)
        else:
            local_error = AIError("local_provider_circuit_open")

        api_key = self._openrouter_key()
        if api_key is None:
            raise AIError("ai_provider_unavailable") from local_error
        estimated_cost = self._openrouter_estimate(messages, max_tokens)
        reservation = self.budget_reserve(estimated_cost, self.settings)
        if reservation is None:
            raise AIError("openrouter_spend_cap_reached") from local_error
        try:
            response_payload = self.transport(
                f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions",
                {
                    "model": self.settings.openrouter_chat_model,
                    "messages": list(messages),
                    "max_tokens": max_tokens,
                    **(
                        {
                            "response_format": {
                                "type": "json_schema",
                                "json_schema": {
                                    "name": "task_response",
                                    "strict": True,
                                    "schema": json_schema,
                                },
                            }
                        }
                        if json_schema
                        else {}
                    ),
                },
                api_key,
            )
            response = _ProviderResult(
                response_payload,
                "openrouter",
                self.settings.openrouter_chat_model,
            )
            parsed = self._parse_chat_result(response, fallback=True)
        except Exception as exc:
            self.budget_settle(reservation, Decimal("0"))
            raise AIError("ai_provider_unavailable") from exc
        self.budget_settle(reservation, parsed.estimated_cost_usd)
        return self._record(parsed, task, job_id)

    def embed(
        self, texts: Sequence[str], task: str = "embedding", job_id: UUID | None = None
    ) -> list[list[float]]:
        if not texts:
            raise ValueError("texts_required")
        if self.settings.ai_mode == "mock":
            mock_vectors = []
            for text in texts:
                seed = text.encode("utf-8")
                vector: list[float] = []
                counter = 0
                while len(vector) < self.settings.ai_embedding_dimension:
                    digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
                    vector.extend(byte / 127.5 - 1 for byte in digest)
                    counter += 1
                mock_vectors.append(vector[: self.settings.ai_embedding_dimension])
            result = ChatResult("", "mock", "deterministic-hash", 0, 0, Decimal("0"), False)
            self._record(result, task, job_id)
            return mock_vectors
        response = self.transport(
            f"{self.settings.ai_local_embedding_base_url.rstrip('/')}/embeddings",
            {"model": self.settings.ai_local_embedding_model, "input": list(texts)},
            self._local_key(),
        )
        data = response.get("data")
        if not isinstance(data, list) or len(data) != len(texts):
            raise AIError("embedding_provider_unavailable")
        vectors: list[list[float]] = []
        for item in data:
            if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                raise AIError("embedding_provider_unavailable")
            vector = [float(value) for value in item["embedding"]]
            if len(vector) != self.settings.ai_embedding_dimension or not all(
                math.isfinite(value) for value in vector
            ):
                raise AIError("embedding_provider_returned_invalid_dimensions")
            vectors.append(vector)
        prompt_tokens, _ = _usage_numbers(response)
        self._record(
            ChatResult(
                "",
                "local",
                self.settings.ai_local_embedding_model,
                prompt_tokens,
                0,
                Decimal("0"),
                False,
            ),
            task,
            job_id,
        )
        return vectors


gateway = AIGateway()
