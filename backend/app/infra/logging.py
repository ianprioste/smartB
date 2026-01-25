"""Structured logging configuration."""
import json
from typing import Any, Dict
import sys
import os
import logging

# Check if we're in debug mode
DEBUG_MODE = os.getenv("LOG_LEVEL") == "DEBUG"

# Always use standard Python logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True,
)

def get_logger(name: str = __name__):
    """Get a standard Python logger."""
    return logging.getLogger(name)


class RequestIdMiddleware:
    """Middleware to add request_id to logs."""
    
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            import uuid
            request_id = str(uuid.uuid4())
            scope["request_id"] = request_id
            
            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"x-request-id", request_id.encode()))
                    message["headers"] = headers
                await send(message)
            
            await self.app(scope, receive, send_with_headers)
        else:
            await self.app(scope, receive, send)
