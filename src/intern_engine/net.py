"""Async HTTP with retry/backoff and per-host concurrency limits.

Connectors talk to the network only through `Net`, which keeps request policy
(retries, backoff, politeness) in one place instead of scattered across every
ATS module.
"""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

# Status codes worth retrying — transient server/rate-limit conditions.
_RETRYABLE = {429, 500, 502, 503, 504}


def _provider(host: str) -> str:
    lowered = host.casefold()
    families = {
        "myworkdayjobs.com": "workday",
        "myworkdaysite.com": "workday",
        "oraclecloud.com": "oracle",
        "greenhouse.io": "greenhouse",
        "smartrecruiters.com": "smartrecruiters",
        "ashbyhq.com": "ashby",
        "lever.co": "lever",
    }
    return next((name for suffix, name in families.items() if lowered.endswith(suffix)), lowered)


class _Permit:
    def __init__(self, semaphores: tuple[asyncio.Semaphore, ...]) -> None:
        self._semaphores = semaphores

    async def __aenter__(self):
        for semaphore in self._semaphores:
            await semaphore.acquire()
        return self

    async def __aexit__(self, *_exc):
        for semaphore in reversed(self._semaphores):
            semaphore.release()


class HostLimiter:
    """Caps how many requests run concurrently against any single host.

    All Greenhouse boards share one host, so a global limit alone would still
    let us hammer it. A per-host semaphore keeps us polite to each provider
    while different hosts still run in parallel.
    """

    def __init__(self, per_host: int = 8, per_provider: int | None = None) -> None:
        self._per_host = per_host
        self._per_provider = per_provider or per_host
        self._sems: dict[str, asyncio.Semaphore] = {}
        self._provider_sems: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, host: str) -> _Permit:
        async with self._lock:
            sem = self._sems.get(host)
            if sem is None:
                sem = asyncio.Semaphore(self._per_host)
                self._sems[host] = sem
            provider = _provider(host)
            provider_sem = self._provider_sems.get(provider)
            if provider_sem is None:
                provider_sem = asyncio.Semaphore(self._per_provider)
                self._provider_sems[provider] = provider_sem
            # A shared host already enforces both scopes.  Avoid acquiring the
            # same semaphore twice if future configuration aliases them.
            return _Permit((provider_sem, sem))


def _backoff(attempt: int, response: httpx.Response | None = None) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After", "").strip()
        if retry_after.isdigit():
            return min(float(retry_after), 120.0)
        if retry_after:
            try:
                when = parsedate_to_datetime(retry_after)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=UTC)
                return min(max((when - datetime.now(UTC)).total_seconds(), 0.0), 120.0)
            except (TypeError, ValueError):
                pass
    return min(2**attempt + random.random(), 20.0)


class Net:
    """A thin client wrapper bound to one httpx session + host limiter."""

    def __init__(self, client: httpx.AsyncClient, limiter: HostLimiter) -> None:
        self._client = client
        self._limiter = limiter

    async def get_json(self, url: str, **kwargs):
        return await self._request("GET", url, **kwargs)

    async def post_json(self, url: str, **kwargs):
        return await self._request("POST", url, **kwargs)

    async def _request(self, method: str, url: str, *, retries: int = 3, **kwargs):
        host = httpx.URL(url).host
        sem = await self._limiter.acquire(host)
        last_error: Exception | None = None

        for attempt in range(retries + 1):
            try:
                async with sem:
                    response = await self._client.request(method, url, **kwargs)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt == retries:
                    raise
                await asyncio.sleep(_backoff(attempt))
                continue

            if response.status_code in _RETRYABLE and attempt < retries:
                await asyncio.sleep(_backoff(attempt, response))
                continue

            response.raise_for_status()
            return response.json()

        # Only reached if every attempt hit a retryable status without resolving.
        raise last_error or httpx.HTTPError(f"request to {url} failed after retries")
