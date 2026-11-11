"""Simple API-key protection for the classroom demo (not a full user-auth system)."""
from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def require_api_key(api_key: str | None = Depends(api_key_header)) -> None:
    if not api_key or not hmac.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )


def require_admin_key(api_key: str | None = Depends(admin_key_header)) -> None:
    if not api_key or not hmac.compare_digest(api_key, settings.admin_api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid administrator key",
        )
