"""Vault AppRole authentication with basic token renewal/re-authentication."""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

import hvac

from app.config import settings

logger = logging.getLogger(__name__)
_lock = threading.RLock()
_client: hvac.Client | None = None
_token_expires_at = 0.0


def _read_approle_credentials() -> dict[str, str]:
    path = Path(settings.vault_approle_file)
    if not path.exists():
        raise RuntimeError(
            f"Vault AppRole file not found: {path}. Start the stack so vault-init can create it."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    role_id = data.get("role_id")
    secret_id = data.get("secret_id")
    if not role_id or not secret_id:
        raise RuntimeError("Vault AppRole file is missing role_id or secret_id")
    return {"role_id": role_id, "secret_id": secret_id}


def _login() -> tuple[hvac.Client, float]:
    credentials = _read_approle_credentials()
    client = hvac.Client(url=settings.vault_addr, timeout=10)
    response = client.auth.approle.login(
        role_id=credentials["role_id"],
        secret_id=credentials["secret_id"],
        mount_point="approle",
    )
    auth_data: dict[str, Any] = response.get("auth") or {}
    if not auth_data.get("client_token"):
        raise RuntimeError("Vault AppRole login did not return a token")
    client.token = auth_data["client_token"]
    lease_duration = int(auth_data.get("lease_duration") or 3600)
    logger.info("Authenticated to Vault using the application's AppRole")
    return client, time.monotonic() + lease_duration


def get_vault_client() -> hvac.Client:
    """Return a cached Vault client, renewing its token when possible."""
    global _client, _token_expires_at
    with _lock:
        now = time.monotonic()
        if _client is not None and now < _token_expires_at - 90:
            return _client

        if _client is not None:
            try:
                response = _client.auth.token.renew_self(increment="1h")
                auth_data = response.get("auth") or {}
                if auth_data.get("client_token"):
                    _client.token = auth_data["client_token"]
                _token_expires_at = time.monotonic() + int(
                    auth_data.get("lease_duration") or 3600
                )
                return _client
            except Exception:
                logger.info("Vault token renewal failed; re-authenticating with AppRole")

        _client, _token_expires_at = _login()
        return _client
