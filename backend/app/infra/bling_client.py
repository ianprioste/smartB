"""Bling API client with OAuth2 and retry logic."""
import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Dict, Any

import httpx

from app.constants import Limits
from app.settings import settings
from app.infra.logging import get_logger
import uuid
import time

logger = get_logger(__name__)


class RateLimiter:
    """
    Rate limiter to respect Bling API limits:
    - 3 requests per second
    - 120,000 requests per day
    """
    def __init__(self, requests_per_second: float = 3.0):
        self.min_interval = 1.0 / requests_per_second  # 0.333 seconds between requests
        self.last_request_time = 0.0
        self.cooldown_until = 0.0
        self._lock: asyncio.Lock | None = None
        self._lock_loop_id: int | None = None

    def _get_lock(self) -> asyncio.Lock:
        """Return an asyncio.Lock bound to the current event loop."""
        loop_id = id(asyncio.get_event_loop())
        if self._lock is None or self._lock_loop_id != loop_id:
            self._lock = asyncio.Lock()
            self._lock_loop_id = loop_id
        return self._lock
    
    async def acquire(self):
        """Wait if necessary to respect rate limit."""
        async with self._get_lock():
            now = time.monotonic()
            time_since_last = now - self.last_request_time
            wait_time = max(0.0, self.cooldown_until - now)
            
            if time_since_last < self.min_interval:
                wait_time = max(wait_time, self.min_interval - time_since_last)
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            self.last_request_time = time.monotonic()

    async def backoff(self, delay_seconds: float):
        """Apply a shared cooldown window after upstream rate limiting."""
        delay_seconds = max(0.0, delay_seconds)
        if delay_seconds == 0:
            return

        async with self._get_lock():
            self.cooldown_until = max(self.cooldown_until, time.monotonic() + delay_seconds)


class BlingAuthError(Exception):
    """Raised when authentication fails."""
    pass


class BlingRefreshTokenExpiredError(BlingAuthError):
    """Raised when refresh token is expired or invalid."""
    pass


class BlingAPIError(Exception):
    """Raised when API call fails."""
    pass


class BlingClient:
    """
    Bling ERP API client with:
    - OAuth2 token management
    - Automatic token refresh
    - Exponential backoff retry
    - Rate limiting (3 req/s)
    - Structured logging
    """
    
    # Global rate limiter shared across all instances
    _rate_limiter = RateLimiter(requests_per_second=3.0)

    def __init__(self, access_token: Optional[str] = None, refresh_token: Optional[str] = None, token_expires_at: Optional[datetime] = None, on_token_refresh=None):
        """Initialize BlingClient.
        
        Args:
            access_token: Access token (can be None for public searches)
            refresh_token: Refresh token (optional)
            token_expires_at: Token expiration datetime (optional)
            on_token_refresh: Callback function(access_token, refresh_token, expires_at) called after token refresh
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = token_expires_at
        self.on_token_refresh = on_token_refresh
        self.request_id = str(uuid.uuid4())
        
        self.client = httpx.AsyncClient(
            base_url=settings.BLING_API_BASE_URL,
            timeout=30.0,
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _is_token_expired(self) -> bool:
        """Check if token is expired or about to expire (5 min buffer)."""
        if not self.token_expires_at:
            return False
        
        buffer = timedelta(minutes=5)
        return datetime.utcnow() >= (self.token_expires_at - buffer)

    def _extract_response_error_detail(self, response: httpx.Response) -> str:
        """Extract best available error detail from Bling response."""
        try:
            data = response.json()
        except Exception:
            data = None

        if isinstance(data, dict):
            if isinstance(data.get("detail"), str):
                return data["detail"]
            if isinstance(data.get("message"), str):
                return data["message"]
            if isinstance(data.get("error"), str):
                return data["error"]
            if isinstance(data.get("error"), dict):
                err = data["error"]
                if isinstance(err.get("message"), str):
                    return err["message"]
                if isinstance(err.get("description"), str):
                    return err["description"]
                if isinstance(err.get("type"), str):
                    return err["type"]

        text = (response.text or "").strip()
        if text:
            return text
        return "Sem detalhes retornados pela API"

    async def _refresh_token(self) -> None:
        """Refresh access token using refresh_token."""
        if not self.refresh_token:
            raise BlingAuthError("No refresh token available")

        logger.info(
            f"token_refresh_attempt - request_id={self.request_id}, refresh_token_present={bool(self.refresh_token)}"
        )

        try:
            async with httpx.AsyncClient() as client:
                _token_url = settings.BLING_TOKEN_PROXY_URL or settings.BLING_TOKEN_URL
                response = await client.post(
                    _token_url,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                        "User-Agent": "Mozilla/5.0 (compatible; smartBling/2.0; +https://app.useruach.com.br)",
                    },
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self.refresh_token,
                        "client_id": settings.BLING_CLIENT_ID,
                        "client_secret": settings.BLING_CLIENT_SECRET,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()

            token_data = response.json()
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data.get("refresh_token", self.refresh_token)
            
            expires_in = token_data.get("expires_in", 3600)
            self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            logger.info(
                f"token_refresh_success - request_id={self.request_id}, new_expiry={self.token_expires_at.isoformat()}"
            )
            
            # Call callback to save new token
            if self.on_token_refresh:
                self.on_token_refresh(self.access_token, self.refresh_token, self.token_expires_at)

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.text
            except:
                pass
            
            status_code = e.response.status_code if hasattr(e, 'response') else None
            logger.error(
                f"token_refresh_failed - request_id={self.request_id}, status_code={status_code}, error={str(e)}, error_detail={error_detail}"
            )
            
            # Detect expired/invalid refresh token (400 Bad Request usually means invalid grant)
            if hasattr(e, 'response') and e.response.status_code == 400:
                raise BlingRefreshTokenExpiredError(
                    "Refresh token expired or invalid. User must re-authenticate via OAuth2 flow."
                )
            raise BlingAuthError(f"Token refresh failed: {e}")
        except Exception as e:
            logger.error(
                f"token_refresh_failed_unexpected - request_id={self.request_id}, error={str(e)}"
            )
            raise BlingAuthError(f"Token refresh failed: {e}")

    def _get_retry_delay_seconds(self, response: httpx.Response, attempt: int, base_delay: int) -> float:
        """Resolve rate-limit delay from response headers or fallback backoff."""
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            retry_after = retry_after.strip()
            try:
                delay_seconds = float(retry_after)
                if delay_seconds > 0:
                    return delay_seconds
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    delay_seconds = (retry_at - datetime.now(timezone.utc)).total_seconds()
                    if delay_seconds > 0:
                        return delay_seconds
                except (TypeError, ValueError, OverflowError):
                    pass

        # Fallback exponential backoff capped to avoid excessive waits.
        return min(float(base_delay * (2 ** attempt)), 60.0)

    async def _retry_with_backoff(
        self,
        method: str,
        path: str,
        max_retries: int = Limits.BLING_RETRY_MAX_ATTEMPTS,
        **kwargs
    ) -> httpx.Response:
        """Execute request with exponential backoff retry."""
        
        base_delay = Limits.BLING_RETRY_INITIAL_DELAY_SECS
        last_exception = None

        for attempt in range(max_retries):
            try:
                # Rate limiting - wait if necessary
                await self._rate_limiter.acquire()
                
                # Check token before request
                if self.access_token and self._is_token_expired():
                    logger.info(
                        f"token_expired_refreshing - request_id={self.request_id}, path={path}"
                    )
                    await self._refresh_token()

                headers = self._get_headers()
                
                # Make request
                if method.upper() == "GET":
                    response = await self.client.get(path, headers=headers, **kwargs)
                elif method.upper() == "POST":
                    response = await self.client.post(path, headers=headers, **kwargs)
                elif method.upper() == "PATCH":
                    response = await self.client.patch(path, headers=headers, **kwargs)
                elif method.upper() == "PUT":
                    response = await self.client.put(path, headers=headers, **kwargs)
                elif method.upper() == "DELETE":
                    response = await self.client.delete(path, headers=headers, **kwargs)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                # Log request
                logger.info(
                    f"api_request - request_id={self.request_id}, method={method}, path={path}, status={response.status_code}, attempt={attempt + 1}"
                )

                # Handle rate limit and server errors
                if response.status_code == 429:
                    delay = self._get_retry_delay_seconds(response, attempt, base_delay)
                    last_exception = BlingAPIError(
                        f"Rate limited (429), retry_after={delay:.1f}s"
                    )
                    logger.warning(
                        "api_request_rate_limited - request_id=%s, method=%s, path=%s, attempt=%s, retry_after_seconds=%.1f",
                        self.request_id,
                        method,
                        path,
                        attempt + 1,
                        delay,
                    )
                    await self._rate_limiter.backoff(delay)
                    if attempt < max_retries - 1:
                        continue
                    raise last_exception
                elif response.status_code >= 500:
                    raise Exception(f"Server error ({response.status_code})")
                elif response.status_code == 404:
                    # Don't retry 404 - resource not found
                    logger.info(
                        f"api_resource_not_found - request_id={self.request_id}, method={method}, path={path}"
                    )
                    raise BlingAPIError(f"Resource not found (404): {path}")
                elif response.status_code == 401:
                    # Unauthorized - try refresh if token available
                    if self.access_token and self.refresh_token:
                        logger.warning(
                            f"unauthorized_refreshing_token - request_id={self.request_id}, path={path}"
                        )
                        await self._refresh_token()
                        continue  # Retry with new token
                    else:
                        raise BlingAuthError("Unauthorized (401) - No valid refresh token available")

                elif response.status_code >= 400:
                    detail = self._extract_response_error_detail(response)
                    logger.error(
                        f"api_client_error_body - request_id={self.request_id}, method={method}, path={path}, status={response.status_code}, body={response.text}"
                    )
                    raise BlingAPIError(
                        f"Client error ({response.status_code}) on {path}: {detail}"
                    )

                response.raise_for_status()
                return response

            except BlingRefreshTokenExpiredError as e:
                # Don't retry if refresh token is expired - fail fast
                logger.error(
                    f"api_request_failed_refresh_token_expired - request_id={self.request_id}, method={method}, path={path}, error={str(e)}"
                )
                raise
            except BlingAPIError:
                # Don't retry explicit client/business errors
                raise
            except Exception as e:
                last_exception = e
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"api_request_retry - request_id={self.request_id}, method={method}, path={path}, attempt={attempt + 1}, delay_seconds={delay}, error={str(e)}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"api_request_failed - request_id={self.request_id}, method={method}, path={path}, attempts={max_retries}, error={str(e)}"
                    )

        raise BlingAPIError(f"Request failed after {max_retries} attempts: {last_exception}")

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET request to Bling API."""
        response = await self._retry_with_backoff("GET", path, params=params)
        return response.json()

    async def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST request to Bling API."""
        response = await self._retry_with_backoff("POST", path, json=payload)
        return response.json()

    async def patch(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH request to Bling API."""
        response = await self._retry_with_backoff("PATCH", path, json=payload)
        return response.json()

    async def put(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """PUT request to Bling API."""
        response = await self._retry_with_backoff("PUT", path, json=payload)
        return response.json()

    async def delete(self, path: str) -> None:
        """DELETE request to Bling API."""
        await self._retry_with_backoff("DELETE", path)

    async def search_products(self, query: str, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        """Search for products in Bling by name.
        
        Args:
            query: Product name or SKU to search
            page: Page number (1-indexed)
            limit: Items per page
            
        Returns:
            Dict with 'data' list and pagination info
        """
        params = {
            "pagina": page,
            "limite": limit,
            "criterio": 1,  # 1 = Últimos incluídos
            # Removido filtro "tipo": "P" para incluir variações
            # P = Produto com estoque | V = Produto variação
        }
        
        # Use name query in Bling; SKU partial matching is handled at API layer.
        params["nome"] = query
            
        return await self.get("/produtos", params=params)

    async def get_product(self, product_id: int) -> Dict[str, Any]:
        """Get product details from Bling."""
        return await self.get(f"/produtos/{product_id}")

    async def get_produtos(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get products from Bling with custom parameters.
        
        Args:
            params: Query parameters (e.g., {"codigo": "SKU123", "limite": 1})
            
        Returns:
            Dict with 'data' list and pagination info
        """
        return await self.get("/produtos", params=params)

    def close(self) -> None:
        """Close HTTP client."""
        self.client.close()
