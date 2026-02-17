"""API key authentication for the backtesting service."""

import os
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key() -> str:
    """Get the configured API key from environment."""
    key = os.environ.get("BACKTESTER_API_KEY", "")
    if not key:
        raise RuntimeError("BACKTESTER_API_KEY environment variable is not set")
    return key


async def verify_api_key(
    api_key: Annotated[str | None, Security(API_KEY_HEADER)],
) -> str:
    """Verify the API key from the request header."""
    expected = os.environ.get("BACKTESTER_API_KEY")
    if not expected:
        # No auth configured — allow all requests
        return "no-auth"

    if api_key is None or api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
