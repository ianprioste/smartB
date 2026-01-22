"""Bling API client with OAuth2 and retry logic."""
import httpx
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.settings import settings
from app.infra.logging import get_logger
import uuid

logger = get_logger(__name__)


class BlingAuthError(Exception):
    """Raised when authentication fails."""
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
    - Structured logging
    """

    def __init__(self, access_token: str, refresh_token: Optional[str] = None, token_expires_at: Optional[datetime] = None):
        """Initialize BlingClient."""
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expires_at = token_expires_at
        self.request_id = str(uuid.uuid4())
        
        self.client = httpx.Client(
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

    def _refresh_token(self) -> None:
        """Refresh access token using refresh_token."""
        if not self.refresh_token:
            raise BlingAuthError("No refresh token available")

        logger.info(
            "token_refresh_attempt",
            request_id=self.request_id,
            refresh_token_present=bool(self.refresh_token),
        )

        try:
            response = httpx.post(
                settings.BLING_TOKEN_URL,
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
                "token_refresh_success",
                request_id=self.request_id,
                new_expiry=self.token_expires_at.isoformat(),
            )

        except httpx.HTTPError as e:
            logger.error(
                "token_refresh_failed",
                request_id=self.request_id,
                error=str(e),
            )
            raise BlingAuthError(f"Token refresh failed: {e}")

    async def _retry_with_backoff(
        self,
        method: str,
        path: str,
        max_retries: int = 3,
        **kwargs
    ) -> httpx.Response:
        """Execute request with exponential backoff retry."""
        
        base_delay = 1
        last_exception = None

        for attempt in range(max_retries):
            try:
                # Check token before request
                if self._is_token_expired():
                    logger.info(
                        "token_expired_refreshing",
                        request_id=self.request_id,
                        path=path,
                    )
                    self._refresh_token()

                headers = self._get_headers()
                
                # Make request
                if method.upper() == "GET":
                    response = self.client.get(path, headers=headers, **kwargs)
                elif method.upper() == "POST":
                    response = self.client.post(path, headers=headers, **kwargs)
                elif method.upper() == "PATCH":
                    response = self.client.patch(path, headers=headers, **kwargs)
                elif method.upper() == "PUT":
                    response = self.client.put(path, headers=headers, **kwargs)
                elif method.upper() == "DELETE":
                    response = self.client.delete(path, headers=headers, **kwargs)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                # Log request
                logger.info(
                    "api_request",
                    request_id=self.request_id,
                    method=method,
                    path=path,
                    status=response.status_code,
                    attempt=attempt + 1,
                )

                # Handle rate limit and server errors
                if response.status_code == 429:
                    raise Exception("Rate limited (429)")
                elif response.status_code >= 500:
                    raise Exception(f"Server error ({response.status_code})")
                elif response.status_code == 401:
                    # Unauthorized - try refresh
                    logger.warn(
                        "unauthorized_refreshing_token",
                        request_id=self.request_id,
                        path=path,
                    )
                    self._refresh_token()
                    continue  # Retry with new token

                response.raise_for_status()
                return response

            except Exception as e:
                last_exception = e
                
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warn(
                        "api_request_retry",
                        request_id=self.request_id,
                        method=method,
                        path=path,
                        attempt=attempt + 1,
                        delay_seconds=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "api_request_failed",
                        request_id=self.request_id,
                        method=method,
                        path=path,
                        attempts=max_retries,
                        error=str(e),
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

    def close(self) -> None:
        """Close HTTP client."""
        self.client.close()
