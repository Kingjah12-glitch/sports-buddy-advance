"""API-Football client with built-in protection for your account.

Why this exists: API-Football suspends keys that go over their plan limits or look abusive.
Every call to the provider in this project goes through fetch_football_data(), which now:

  1. Caches answers (same request within CACHE_SECONDS = no new provider call).
  2. Enforces a daily budget      (API_DAILY_BUDGET, default 40 calls per UTC day).
  3. Enforces a per-minute limit  (API_MAX_PER_MINUTE, default 5).
  4. Stops calling when the provider says "slow down" or "denied" (circuit breaker), and when
     the provider's own remaining-requests header says you are nearly out.

When a limit is hit it raises SportsAPIError; the rest of the app already handles that by
falling back to saved data, so visitors never cause a ban.
"""
import asyncio
import os
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.config import API_FOOTBALL_BASE_URL, API_FOOTBALL_KEY


class SportsAPIError(Exception):
    pass


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


CACHE_SECONDS = _int_env("API_CACHE_SECONDS", 600)          # normal answers
LIVE_CACHE_SECONDS = 60                                       # anything asking for live matches
CACHE_MAX_ENTRIES = 200
DAILY_BUDGET = _int_env("API_DAILY_BUDGET", 40)
MAX_PER_MINUTE = _int_env("API_MAX_PER_MINUTE", 5)
KEEP_BACK_REQUESTS = 3        # stop when the provider says this few requests are left today

_cache: dict = {}             # key -> (stored_at_monotonic, data)
_calls_today = {"day": None, "count": 0}
_recent_calls: list = []      # monotonic timestamps of calls in the last minute
_blocked_until = 0.0          # monotonic time until which we refuse to call the provider
_blocked_reason = ""
_lock = asyncio.Lock()


def reset_guard() -> None:
    """Clear cache, counters and breaker (used by tests)."""
    global _blocked_until, _blocked_reason
    _cache.clear()
    _recent_calls.clear()
    _calls_today.update({"day": None, "count": 0})
    _blocked_until, _blocked_reason = 0.0, ""


def usage() -> dict:
    """Small summary for the /status page."""
    today = datetime.now(timezone.utc).date().isoformat()
    used = _calls_today["count"] if _calls_today["day"] == today else 0
    wait = max(0, int(_blocked_until - time.monotonic()))
    return {"calls_today": used, "daily_budget": DAILY_BUDGET,
            "blocked_for_seconds": wait, "blocked_reason": _blocked_reason if wait else ""}


def _seconds_until_utc_midnight() -> int:
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


def _block(seconds: int, reason: str) -> None:
    global _blocked_until, _blocked_reason
    _blocked_until = max(_blocked_until, time.monotonic() + seconds)
    _blocked_reason = reason


def _cache_key(endpoint: str, params: dict | None) -> tuple:
    return (endpoint.strip("/"), tuple(sorted((str(k), str(v)) for k, v in (params or {}).items())))


def _cache_get(key: tuple, ttl: int):
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    return None


def _cache_put(key: tuple, data) -> None:
    if len(_cache) >= CACHE_MAX_ENTRIES:
        oldest = min(_cache, key=lambda k: _cache[k][0])
        _cache.pop(oldest, None)
    _cache[key] = (time.monotonic(), data)


def _check_allowed() -> None:
    """Raise SportsAPIError if we must not call the provider right now."""
    now = time.monotonic()
    if now < _blocked_until:
        raise SportsAPIError(f"Provider calls paused for {int(_blocked_until - now)}s ({_blocked_reason}).")
    today = datetime.now(timezone.utc).date().isoformat()
    if _calls_today["day"] != today:
        _calls_today.update({"day": today, "count": 0})
    if _calls_today["count"] >= DAILY_BUDGET:
        raise SportsAPIError(f"Daily request budget reached ({DAILY_BUDGET}); using saved data.")
    _recent_calls[:] = [t for t in _recent_calls if now - t < 60]
    if len(_recent_calls) >= MAX_PER_MINUTE:
        raise SportsAPIError("Per-minute request limit reached; try again shortly.")


def _read_rate_headers(response: httpx.Response) -> None:
    """API-Football tells us how many requests are left today; stop before we hit zero."""
    left = response.headers.get("x-ratelimit-requests-remaining")
    try:
        if left is not None and int(left) <= KEEP_BACK_REQUESTS:
            _block(_seconds_until_utc_midnight(), "provider quota almost used up")
    except ValueError:
        pass


async def fetch_football_data(endpoint: str, params: dict | None = None):
    if not API_FOOTBALL_KEY:
        raise SportsAPIError("API key is missing. Configure API_FOOTBALL_KEY in .env.")

    key = _cache_key(endpoint, params)
    ttl = LIVE_CACHE_SECONDS if "live" in (params or {}) else CACHE_SECONDS
    cached = _cache_get(key, ttl)
    if cached is not None:
        return cached

    url = f"{API_FOOTBALL_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}

    async with _lock:                      # one provider call at a time; waiters reuse the cache
        cached = _cache_get(key, ttl)
        if cached is not None:
            return cached
        _check_allowed()
        _calls_today["count"] += 1         # count the attempt, even if it fails
        _recent_calls.append(time.monotonic())

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers, params=params or {})
            _read_rate_headers(response)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as error:
            code = error.response.status_code
            if code == 429:
                _block(300, "provider said too many requests")
            elif code in (401, 403, 499):
                _block(3600, f"provider refused the key (HTTP {code}); check your account")
            raise SportsAPIError(f"Sports provider returned HTTP {code}.") from error
        except httpx.RequestError as error:
            raise SportsAPIError("Could not connect to the sports data provider.") from error
        except ValueError as error:
            raise SportsAPIError("The sports provider returned invalid JSON.") from error

        errors = data.get("errors")
        if errors:
            text = str(errors).lower()
            if "ratelimit" in text:
                _block(90, "provider per-minute limit")
            elif "request" in text and "limit" in text:
                _block(_seconds_until_utc_midnight(), "provider daily limit reached")
            elif "token" in text or "access" in text or "suspend" in text or "disabled" in text:
                _block(3600, "provider rejected the key or account")
            raise SportsAPIError(f"Sports provider rejected the request: {errors}")

        _cache_put(key, data)
        return data
