"""Envelope encryption: Vault Transit wraps a DEK; AES-256-GCM encrypts app data."""
from __future__ import annotations

import base64
import os
import re
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass

import hvac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings

_VERSION_RE = re.compile(r"^vault:v(\d+):")


class DekCache:
    """Short-lived unwrapped DEKs, keyed by KEK name and wrapped ciphertext.

    Disabled when DEK_CACHE_TTL_SECONDS is 0 (the default). Enabling it is
    configuration D'. A hit does not call Vault, so min_decryption_version
    is not enforced again until the entry expires or the process restarts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: OrderedDict[str, tuple[float, bytes]] = OrderedDict()

    def get(self, key: str) -> bytes | None:
        ttl = settings.dek_cache_ttl_seconds
        if ttl <= 0:
            return None
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, dek = item
            if expires_at <= now:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return dek

    def put(self, key: str, dek: bytes) -> None:
        ttl = settings.dek_cache_ttl_seconds
        if ttl <= 0:
            return
        now = time.monotonic()
        with self._lock:
            self._items[key] = (now + ttl, dek)
            self._items.move_to_end(key)
            while len(self._items) > settings.dek_cache_max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


dek_cache = DekCache()


def _cache_key(kek_name: str, encrypted_dek: str) -> str:
    return f"{kek_name}\n{encrypted_dek}"


@dataclass(frozen=True)
class EncryptedPayload:
    ciphertext: bytes
    nonce: bytes
    encrypted_dek: str
    kek_name: str
    kek_version: int | None


def kek_version_from_ciphertext(encrypted_dek: str) -> int | None:
    """Read the KEK version embedded in a Vault Transit ciphertext (`vault:vN:...`)."""
    match = _VERSION_RE.match(encrypted_dek)
    return int(match.group(1)) if match else None


def associated_data(record_id: uuid.UUID, record_type: str) -> bytes:
    """Bind ciphertext to the record ID and type to prevent swapping records."""
    return f"{record_id}:{record_type}".encode("utf-8")


def encrypt_with_dek(
    plaintext: str,
    dek: bytes,
    nonce: bytes,
    aad: bytes,
) -> bytes:
    if len(dek) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte DEK")
    if len(nonce) != 12:
        raise ValueError("AES-GCM nonce must be 12 bytes")
    return AESGCM(dek).encrypt(nonce, plaintext.encode("utf-8"), aad)


def decrypt_with_dek(
    ciphertext: bytes,
    dek: bytes,
    nonce: bytes,
    aad: bytes,
) -> str:
    if len(dek) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte DEK")
    return AESGCM(dek).decrypt(nonce, ciphertext, aad).decode("utf-8")


def encrypt_sensitive_value(
    client: hvac.Client,
    plaintext: str,
    record_id: uuid.UUID,
    record_type: str,
) -> EncryptedPayload:
    """Generate a DEK in Vault, encrypt data locally, and retain only wrapped DEK."""
    response = client.secrets.transit.generate_data_key(
        name=settings.vault_transit_key,
        key_type="plaintext",
        bits=256,
        mount_point=settings.vault_transit_mount,
    )
    data = response["data"]
    dek = base64.b64decode(data["plaintext"], validate=True)
    encrypted_dek = data["ciphertext"]
    nonce = os.urandom(12)
    ciphertext = encrypt_with_dek(
        plaintext=plaintext,
        dek=dek,
        nonce=nonce,
        aad=associated_data(record_id, record_type),
    )
    version = kek_version_from_ciphertext(encrypted_dek)
    return EncryptedPayload(
        ciphertext=ciphertext,
        nonce=nonce,
        encrypted_dek=encrypted_dek,
        kek_name=settings.vault_transit_key,
        kek_version=version,
    )


def unwrap_dek(client: hvac.Client, *, encrypted_dek: str, kek_name: str) -> bytes:
    """Return the 32-byte DEK, using the in-process cache when it is enabled."""
    key = _cache_key(kek_name, encrypted_dek)
    cached = dek_cache.get(key)
    if cached is not None:
        return cached
    response = client.secrets.transit.decrypt_data(
        name=kek_name,
        ciphertext=encrypted_dek,
        mount_point=settings.vault_transit_mount,
    )
    dek = base64.b64decode(response["data"]["plaintext"], validate=True)
    if len(dek) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte DEK")
    dek_cache.put(key, dek)
    return dek


def decrypt_sensitive_value(
    client: hvac.Client,
    *,
    ciphertext: bytes,
    nonce: bytes,
    encrypted_dek: str,
    kek_name: str,
    record_id: uuid.UUID,
    record_type: str,
) -> str:
    """Unwrap the DEK through Vault, then authenticate/decrypt the stored data."""
    dek = unwrap_dek(client, encrypted_dek=encrypted_dek, kek_name=kek_name)
    return decrypt_with_dek(
        ciphertext=ciphertext,
        dek=dek,
        nonce=nonce,
        aad=associated_data(record_id, record_type),
    )
