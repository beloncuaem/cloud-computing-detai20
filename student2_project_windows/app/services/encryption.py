"""Envelope encryption: Vault Transit wraps a DEK; AES-256-GCM encrypts app data."""
from __future__ import annotations

import base64
import os
import re
import uuid
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings

_VERSION_RE = re.compile(r"^vault:v(\d+):")


@dataclass(frozen=True)
class EncryptedPayload:
    ciphertext: bytes
    nonce: bytes
    encrypted_dek: str
    kek_name: str
    kek_version: int | None


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
    match = _VERSION_RE.match(encrypted_dek)
    version = int(match.group(1)) if match else None
    return EncryptedPayload(
        ciphertext=ciphertext,
        nonce=nonce,
        encrypted_dek=encrypted_dek,
        kek_name=settings.vault_transit_key,
        kek_version=version,
    )


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
    response = client.secrets.transit.decrypt_data(
        name=kek_name,
        ciphertext=encrypted_dek,
        mount_point=settings.vault_transit_mount,
    )
    dek = base64.b64decode(response["data"]["plaintext"], validate=True)
    return decrypt_with_dek(
        ciphertext=ciphertext,
        dek=dek,
        nonce=nonce,
        aad=associated_data(record_id, record_type),
    )
