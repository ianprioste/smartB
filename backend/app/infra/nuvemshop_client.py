"""Nuvemshop (Tiendanube) API client with rate limiting and retry logic."""
import asyncio
import time
from typing import Any, Dict, Optional

import httpx

from app.settings import settings
from app.infra.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://api.nuvemshop.com.br/v1/{store_id}"


class NuvemshopAPIError(Exception):
    """Raised when a Nuvemshop API call fails."""
    pass


class _RateLimiter:
    """Simple per-second rate limiter (2 req/s conservative)."""
    def __init__(self, rps: float = 2.0):
        self._interval = 1.0 / rps
        self._last = 0.0
        self._lock: Optional[asyncio.Lock] = None
        self._loop_id: Optional[int] = None

    def _get_lock(self) -> asyncio.Lock:
        loop_id = id(asyncio.get_event_loop())
        if self._lock is None or self._loop_id != loop_id:
            self._lock = asyncio.Lock()
            self._loop_id = loop_id
        return self._lock

    async def acquire(self):
        async with self._get_lock():
            now = time.monotonic()
            wait = self._interval - (now - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


class NuvemshopClient:
    """Async client for the Nuvemshop REST API."""

    _rate_limiter = _RateLimiter(rps=2.0)

    def __init__(
        self,
        access_token: Optional[str] = None,
        store_id: Optional[str] = None,
    ):
        self.access_token = access_token or settings.NUVEMSHOP_ACCESS_TOKEN
        self.store_id = store_id or settings.NUVEMSHOP_STORE_ID
        if not self.access_token or not self.store_id:
            raise NuvemshopAPIError(
                "NUVEMSHOP_ACCESS_TOKEN and NUVEMSHOP_STORE_ID must be configured"
            )
        base = _BASE_URL.format(store_id=self.store_id)
        self._client = httpx.AsyncClient(base_url=base, timeout=30.0)

    def _headers(self) -> Dict[str, str]:
        # Nuvemshop uses "Authentication" (NOT "Authorization")
        return {
            "Authentication": f"bearer {self.access_token}",
            "Content-Type": "application/json",
            "User-Agent": "smartBling/1.0",
        }

    async def _request(
        self,
        method: str,
        path: str,
        json: Any = None,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Any:
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            await self._rate_limiter.acquire()
            try:
                resp = await self._client.request(
                    method,
                    path,
                    headers=self._headers(),
                    json=json,
                    params=params,
                )
                if resp.status_code == 429:
                    delay = 2 ** attempt
                    logger.warning(
                        "nuvemshop_rate_limited path=%s attempt=%s retry_in=%ss",
                        path, attempt + 1, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                if resp.status_code >= 400:
                    detail = resp.text[:500] if resp.text else str(resp.status_code)
                    raise NuvemshopAPIError(
                        f"Nuvemshop {method} {path} → {resp.status_code}: {detail}"
                    )
                if resp.status_code == 204:
                    return None
                return resp.json()
            except NuvemshopAPIError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise NuvemshopAPIError(f"Nuvemshop request failed: {exc}") from exc
        raise NuvemshopAPIError(f"Nuvemshop request failed after retries: {last_exc}")

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: Any = None) -> Any:
        return await self._request("POST", path, json=json)

    async def put(self, path: str, json: Any = None) -> Any:
        return await self._request("PUT", path, json=json)

    async def patch(self, path: str, json: Any = None) -> Any:
        return await self._request("PATCH", path, json=json)

    async def close(self):
        await self._client.aclose()
