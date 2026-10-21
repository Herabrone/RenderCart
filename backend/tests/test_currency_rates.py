import json

import pytest
from fastapi.testclient import TestClient

from rendercart.business import currency_rates

_ECB_SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
 xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <Cube><Cube time="2026-10-16">
    <Cube currency="USD" rate="1.1642"/><Cube currency="CAD" rate="1.6032"/>
  </Cube></Cube>
</gesmes:Envelope>"""


def test_parse_ecb_reference_rates_and_base() -> None:
    result = currency_rates.parse_ecb_rates(_ECB_SAMPLE)

    assert result == {
        "base": "EUR",
        "as_of": "2026-10-16",
        "source": "ECB",
        "rates": {"EUR": 1.0, "USD": 1.1642, "CAD": 1.6032},
    }


@pytest.mark.parametrize(
    "xml",
    [
        b"",
        b"<!DOCTYPE x [<!ENTITY e SYSTEM 'file:///etc/passwd'>]><x>&e;</x>",
        b"<root><Cube time='not-a-date'/></root>",
        b"<root><Cube time='2026-10-16'><Cube currency='USD' rate='NaN'/></Cube></root>",
        b"<root><Cube time='2026-10-16'><Cube currency='US' rate='1.2'/></Cube></root>",
    ],
)
def test_reject_malformed_or_unsafe_ecb_payloads(xml: bytes) -> None:
    with pytest.raises(currency_rates.CurrencyRatesUnavailable):
        currency_rates.parse_ecb_rates(xml)


def test_rates_are_cached_and_cached_payload_is_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}
            self.expirations: dict[str, int] = {}

        def get(self, key: str) -> str | None:
            return self.values.get(key)

        def set(self, key: str, value: str, *, ex: int) -> None:
            self.values[key] = value
            self.expirations[key] = ex

    cache = FakeRedis()
    calls = 0

    def fetch() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return currency_rates.parse_ecb_rates(_ECB_SAMPLE)

    monkeypatch.setattr(currency_rates, "currency_cache", cache)
    monkeypatch.setattr(currency_rates, "fetch_ecb_rates", fetch)

    current = currency_rates.get_currency_rates(refresh=True)
    reused = currency_rates.get_currency_rates()

    assert current["stale"] is False
    assert reused == current
    assert calls == 1
    assert cache.expirations[currency_rates._CACHE_KEY] == 86_400
    assert cache.expirations[currency_rates._STALE_KEY] == 604_800


def test_stale_cache_survives_an_ecb_outage(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            stale = currency_rates.parse_ecb_rates(_ECB_SAMPLE)
            self.payload = json.dumps(stale)

        def get(self, key: str) -> str | None:
            return self.payload if key == currency_rates._STALE_KEY else None

        def set(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("an upstream failure must not overwrite the last-good cache")

    def failed_fetch() -> dict[str, object]:
        raise currency_rates.CurrencyRatesUnavailable("upstream down")

    monkeypatch.setattr(currency_rates, "currency_cache", FakeRedis())
    monkeypatch.setattr(currency_rates, "fetch_ecb_rates", failed_fetch)

    result = currency_rates.get_currency_rates(refresh=True)

    assert result["stale"] is True
    assert result["as_of"] == "2026-10-16"


def test_public_rates_endpoint_returns_cacheable_data(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        currency_rates,
        "get_currency_rates",
        lambda: {
            "base": "EUR",
            "as_of": "2026-10-16",
            "source": "ECB",
            "rates": {"EUR": 1.0},
            "stale": False,
        },
    )

    response = client.get("/api/currency-rates")

    assert response.status_code == 200
    assert response.json()["source"] == "ECB"
    assert response.headers["cache-control"] == "public, max-age=3600"
