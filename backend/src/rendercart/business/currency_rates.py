"""Cached public reference rates from the European Central Bank."""

import json
import math
import re
import ssl
import xml.etree.ElementTree as ET
from datetime import date
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
from fastapi import APIRouter, HTTPException, Response
from redis import Redis
from redis.exceptions import RedisError

from rendercart.core.config import get_settings

router = APIRouter(prefix="/api/currency-rates", tags=["currency rates"])
_ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
_CACHE_KEY = "public:currency-rates:ecb:v1"
_STALE_KEY = "public:currency-rates:ecb:last-good:v1"
_CACHE_SECONDS = 24 * 60 * 60
_STALE_SECONDS = 7 * 24 * 60 * 60
_MAX_XML_BYTES = 256_000
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
_settings = get_settings()
_broker_url = _settings.celery_broker_url or _settings.redis_url.rsplit("/", 1)[0] + "/1"
currency_cache = Redis.from_url(_broker_url, decode_responses=True)


class CurrencyRatesUnavailable(RuntimeError):
    """No valid current or cached ECB rates are available."""


def parse_ecb_rates(xml: bytes) -> dict[str, object]:
    if not xml or len(xml) > _MAX_XML_BYTES:
        raise CurrencyRatesUnavailable("Invalid ECB response size")
    upper = xml.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise CurrencyRatesUnavailable("Unexpected XML declarations")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise CurrencyRatesUnavailable("Malformed ECB XML") from exc

    rate_date: str | None = None
    rates: dict[str, float] = {"EUR": 1.0}
    for element in root.iter():
        observed_date = element.attrib.get("time")
        if observed_date:
            try:
                rate_date = date.fromisoformat(observed_date).isoformat()
            except ValueError as exc:
                raise CurrencyRatesUnavailable("Invalid ECB rate date") from exc
        code = element.attrib.get("currency")
        raw_rate = element.attrib.get("rate")
        if code is None and raw_rate is None:
            continue
        if code is None or raw_rate is None or not _CURRENCY_CODE.fullmatch(code):
            raise CurrencyRatesUnavailable("Invalid ECB currency entry")
        try:
            rate = float(raw_rate)
        except ValueError as exc:
            raise CurrencyRatesUnavailable("Invalid ECB rate value") from exc
        if not math.isfinite(rate) or rate <= 0 or code == "EUR":
            raise CurrencyRatesUnavailable("Invalid ECB rate value")
        rates[code] = rate

    if rate_date is None or len(rates) < 2:
        raise CurrencyRatesUnavailable("ECB response contains no rates")
    return {"base": "EUR", "as_of": rate_date, "source": "ECB", "rates": rates}


def fetch_ecb_rates() -> dict[str, object]:
    request = Request(
        _ECB_URL,
        headers={"Accept": "application/xml", "User-Agent": "RenderCart/1.0"},
    )
    try:
        with urlopen(
            request,
            timeout=5,
            context=ssl.create_default_context(cafile=certifi.where()),
        ) as response:  # noqa: S310 - fixed official ECB URL
            return parse_ecb_rates(response.read(_MAX_XML_BYTES + 1))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise CurrencyRatesUnavailable("ECB request failed") from exc


def _decode_cached(raw: str, *, stale: bool) -> dict[str, object] | None:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(value, dict)
        or value.get("base") != "EUR"
        or value.get("source") != "ECB"
        or not isinstance(value.get("as_of"), str)
        or not isinstance(value.get("rates"), dict)
    ):
        return None
    return {**value, "stale": stale}


def get_currency_rates(*, refresh: bool = False) -> dict[str, object]:
    if not refresh:
        try:
            cached = cast(str | None, currency_cache.get(_CACHE_KEY))
            if cached:
                decoded = _decode_cached(cached, stale=False)
                if decoded:
                    return decoded
        except RedisError:
            pass

    try:
        rates = fetch_ecb_rates()
    except CurrencyRatesUnavailable:
        try:
            stale = cast(str | None, currency_cache.get(_STALE_KEY))
        except RedisError:
            stale = None
        decoded = _decode_cached(stale, stale=True) if stale else None
        if decoded:
            return decoded
        raise

    serialized = json.dumps(rates, separators=(",", ":"))
    try:
        currency_cache.set(_CACHE_KEY, serialized, ex=_CACHE_SECONDS)
        currency_cache.set(_STALE_KEY, serialized, ex=_STALE_SECONDS)
    except RedisError:
        # The endpoint remains useful if Redis is temporarily unavailable.
        pass
    return {**rates, "stale": False}


@router.get("")
def currency_rates(response: Response) -> dict[str, object]:
    try:
        payload = get_currency_rates()
        cache_age = 300 if payload["stale"] else 3600
        response.headers["Cache-Control"] = f"public, max-age={cache_age}"
        return payload
    except CurrencyRatesUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail="Currency rates are temporarily unavailable",
        ) from exc
