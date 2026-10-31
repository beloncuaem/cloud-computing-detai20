"""Environment-driven settings for the local classroom demo."""
from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://app_user:local_app_password@localhost:5432/encryption_db",
    )
    use_vault_db_creds: bool = _as_bool(os.getenv("USE_VAULT_DB_CREDS"), False)
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "encryption_db")
    db_rotation_interval_seconds: int = max(
        60, int(os.getenv("DB_ROTATION_INTERVAL_SECONDS", "1800"))
    )

    vault_addr: str = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
    vault_approle_file: str = os.getenv(
        "VAULT_APPROLE_FILE", "./vault-credentials.json"
    )
    vault_transit_mount: str = os.getenv("VAULT_TRANSIT_MOUNT", "transit")
    vault_transit_key: str = os.getenv("VAULT_TRANSIT_KEY", "app-data-key")
    vault_database_mount: str = os.getenv("VAULT_DATABASE_MOUNT", "database")
    vault_database_role: str = os.getenv("VAULT_DATABASE_ROLE", "app-role")
    vault_approle_name: str = os.getenv("VAULT_APPROLE_NAME", "student2-app")

    api_key: str = os.getenv("API_KEY", "local-demo-api-key-change-me")
    admin_api_key: str = os.getenv("ADMIN_API_KEY", "local-demo-admin-key-change-me")


settings = Settings()
