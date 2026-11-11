"""Unit tests for the AES-GCM helper without requiring a running Vault instance."""
import os

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.services.encryption import decrypt_with_dek, encrypt_with_dek, kek_version_from_ciphertext


def test_encrypt_decrypt_round_trip() -> None:
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    aad = b"record-123:customer_phone"
    original = "0901234567"

    ciphertext = encrypt_with_dek(original, key, nonce, aad)

    assert ciphertext != original.encode("utf-8")
    assert decrypt_with_dek(ciphertext, key, nonce, aad) == original


def test_tampered_ciphertext_fails_authentication() -> None:
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    aad = b"record-123:customer_phone"
    ciphertext = bytearray(encrypt_with_dek("0901234567", key, nonce, aad))
    ciphertext[0] ^= 1

    with pytest.raises(InvalidTag):
        decrypt_with_dek(bytes(ciphertext), key, nonce, aad)


def test_wrong_associated_data_fails_authentication() -> None:
    key = AESGCM.generate_key(bit_length=256)
    nonce = os.urandom(12)
    ciphertext = encrypt_with_dek("0901234567", key, nonce, b"record-1:phone")

    with pytest.raises(InvalidTag):
        decrypt_with_dek(ciphertext, key, nonce, b"record-2:phone")


def test_kek_version_is_read_from_transit_prefix() -> None:
    assert kek_version_from_ciphertext("vault:v2:abc") == 2
    assert kek_version_from_ciphertext("not-a-vault-ciphertext") is None


def test_key_and_nonce_sizes_are_checked() -> None:
    with pytest.raises(ValueError):
        encrypt_with_dek("abc", b"short", os.urandom(12), b"aad")
    with pytest.raises(ValueError):
        encrypt_with_dek("abc", os.urandom(32), b"short", b"aad")
