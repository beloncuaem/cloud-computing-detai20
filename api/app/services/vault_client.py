"""Vault AppRole authentication with token reuse across processes.

The workload SecretID is single-use. The first login stores the resulting
client token beside the SecretID so later processes (the API, the privilege
checker) reuse that token instead of spending the SecretID again. A second
login with the same SecretID is rejected by Vault.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import hvac

from app.config import settings

logger = logging.getLogger(__name__)
_lock = threading.RLock()
_client: hvac.Client | None = None
_token_expires_at = 0.0


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Vault credential file is not a JSON object: {path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    """Exclusive lock so two processes cannot both spend a one-use SecretID."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + 15
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            if time.monotonic() > deadline:
                raise TimeoutError(f"Timed out waiting for credential lock {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            lock_path.unlink()
        except OSError:
            pass


def _client_from_token(token: str) -> tuple[hvac.Client, float]:
    client = hvac.Client(url=settings.vault_addr, token=token, timeout=10)
    if not client.is_authenticated():
        raise RuntimeError("Stored Vault token is not authenticated")
    lookup = client.auth.token.lookup_self()
    ttl = int((lookup.get("data") or {}).get("ttl") or 3600)
    return client, time.monotonic() + ttl


def _login_with_secret(role_id: str, secret_id: str) -> tuple[hvac.Client, float, str]:
    client = hvac.Client(url=settings.vault_addr, timeout=10)
    response = client.auth.approle.login(
        role_id=role_id,
        secret_id=secret_id,
        mount_point="approle",
    )
    auth_data: dict[str, Any] = response.get("auth") or {}
    token = auth_data.get("client_token")
    if not token:
        raise RuntimeError("Vault AppRole login did not return a token")
    client.token = token
    lease_duration = int(auth_data.get("lease_duration") or 3600)
    return client, time.monotonic() + lease_duration, token


def _client_from_approle_file(credentials_file: str) -> hvac.Client:
    path = Path(credentials_file)
    if not path.exists():
        raise RuntimeError(f"Vault AppRole file not found: {path}")
    with _file_lock(path):
        data = _read_json(path)
        stored = data.get("client_token")
        if stored:
            try:
                client, _expires = _client_from_token(stored)
                return client
            except Exception:
                logger.info("Stored token in %s is not usable; trying SecretID login", path)
        role_id = data.get("role_id")
        secret_id = data.get("secret_id")
        if not role_id or not secret_id:
            raise RuntimeError("Vault AppRole file is missing role_id or secret_id")
        client, _expires, token = _login_with_secret(role_id, secret_id)
        data["client_token"] = token
        _write_json(path, data)
        logger.info("Authenticated to Vault with a one-use SecretID from %s", path.name)
        return client


def _login() -> tuple[hvac.Client, float]:
    path = Path(settings.vault_approle_file)
    if not path.exists():
        raise RuntimeError(
            f"Vault AppRole file not found: {path}. Start the stack so vault-init can create it."
        )
    with _file_lock(path):
        data = _read_json(path)
        stored = data.get("client_token")
        if stored:
            try:
                return _client_from_token(stored)
            except Exception:
                logger.info("Stored workload token is not usable; logging in with SecretID")
        role_id = data.get("role_id")
        secret_id = data.get("secret_id")
        if not role_id or not secret_id:
            raise RuntimeError("Vault AppRole file is missing role_id or secret_id")
        client, expires, token = _login_with_secret(role_id, secret_id)
        data["client_token"] = token
        _write_json(path, data)
        logger.info("Authenticated to Vault using the application's AppRole")
        return client, expires


def get_vault_client() -> hvac.Client:
    """Return a cached workload Vault client, renewing its token when possible."""
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


def get_operator_client() -> hvac.Client:
    """Authenticate as the operator identity, never as the workload AppRole.

    The operator credential file is mounted only into vault-init. The API
    container does not have it, so a workload process cannot rotate the KEK.
    """
    operator_file = os.getenv("VAULT_OPERATOR_FILE", "")
    if operator_file and Path(operator_file).exists():
        return _client_from_approle_file(operator_file)

    token = os.getenv("VAULT_OPERATOR_TOKEN") or os.getenv("VAULT_SETUP_TOKEN") or ""
    if token:
        client = hvac.Client(url=settings.vault_addr, token=token, timeout=10)
        if not client.is_authenticated():
            raise RuntimeError("Operator token was rejected by Vault")
        return client

    raise RuntimeError(
        "Operator identity is not available in this process. "
        "Run the script from the vault-init service, which holds the operator AppRole."
    )
