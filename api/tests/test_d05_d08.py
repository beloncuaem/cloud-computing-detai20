"""Regression checks for D-05 (least-privilege vault_admin) and D-08 (DEK cache)."""
from __future__ import annotations

import base64
from pathlib import Path

import pytest

from app.config import settings
from app.services.encryption import dek_cache, unwrap_dek

API_ROOT = Path(__file__).resolve().parents[1]


def test_vault_admin_sql_is_not_superuser() -> None:
    sql = (API_ROOT / "sql" / "00-create-roles.sql").read_text(encoding="utf-8")
    assert "LOGIN SUPERUSER" not in sql
    assert "NOSUPERUSER" in sql
    assert "NOINHERIT" in sql
    assert "CREATEROLE" in sql
    assert "app_writer" in sql
    assert "WITH ADMIN OPTION" in sql


def test_schema_grants_dml_to_app_writer_not_vault_admin() -> None:
    sql = (API_ROOT / "sql" / "01-schema.sql").read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE sensitive_records TO app_writer;" in sql
    assert "TO vault_admin" not in sql


def test_database_role_creation_only_grants_app_writer() -> None:
    script = (API_ROOT / "scripts" / "setup_vault.py").read_text(encoding="utf-8")
    assert 'GRANT app_writer TO "{{name}}";' in script
    assert "revocation_statements" in script
    assert "sensitive_records" not in script.split("def configure_database_engine")[1].split("def _enable_approle")[0]


class _Transit:
    def __init__(self, plaintext: bytes) -> None:
        self.plaintext = plaintext
        self.calls = 0

    def decrypt_data(self, **_kwargs: object) -> dict:
        self.calls += 1
        return {"data": {"plaintext": base64.b64encode(self.plaintext).decode("ascii")}}


class _Client:
    def __init__(self, transit: _Transit) -> None:
        self.secrets = self
        self.transit = transit


def test_dek_cache_skips_second_vault_unwrap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dek_cache_ttl_seconds", 120)
    monkeypatch.setattr(settings, "dek_cache_max_entries", 8)
    dek_cache.clear()
    transit = _Transit(b"k" * 32)
    client = _Client(transit)
    first = unwrap_dek(client, encrypted_dek="vault:v1:abc", kek_name="app-data-key")
    second = unwrap_dek(client, encrypted_dek="vault:v1:abc", kek_name="app-data-key")
    assert first == second == b"k" * 32
    assert transit.calls == 1
    dek_cache.clear()


def test_dek_cache_disabled_calls_vault_every_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "dek_cache_ttl_seconds", 0)
    dek_cache.clear()
    transit = _Transit(b"k" * 32)
    client = _Client(transit)
    unwrap_dek(client, encrypted_dek="vault:v1:abc", kek_name="app-data-key")
    unwrap_dek(client, encrypted_dek="vault:v1:abc", kek_name="app-data-key")
    assert transit.calls == 2
