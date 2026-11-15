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
    # "require" bật TLS phía client khi PostgreSQL chạy ssl=on (T13).
    db_sslmode: str = os.getenv("DB_SSLMODE", "disable")
    db_rotation_interval_seconds: int = max(
        60, int(os.getenv("DB_ROTATION_INTERVAL_SECONDS", "1800"))
    )
    # Sized for the 100-VU benchmark. Each worker has its own pool.
    db_pool_size: int = max(1, int(os.getenv("DB_POOL_SIZE", "20")))
    db_max_overflow: int = max(0, int(os.getenv("DB_MAX_OVERFLOW", "20")))
    # 0 disables the DEK cache. A positive TTL is configuration D': repeated
    # unwraps of the same wrapped DEK skip Vault. While an entry is live,
    # min_decryption_version is not consulted for that ciphertext.
    dek_cache_ttl_seconds: int = max(0, int(os.getenv("DEK_CACHE_TTL_SECONDS", "0")))
    dek_cache_max_entries: int = max(1, int(os.getenv("DEK_CACHE_MAX_ENTRIES", "1024")))

    vault_addr: str = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
    vault_approle_file: str = os.getenv(
        "VAULT_APPROLE_FILE", "./vault-credentials.json"
    )
    vault_transit_mount: str = os.getenv("VAULT_TRANSIT_MOUNT", "transit")
    vault_transit_key: str = os.getenv("VAULT_TRANSIT_KEY", "app-data-key")
    vault_database_mount: str = os.getenv("VAULT_DATABASE_MOUNT", "database")
    vault_database_role: str = os.getenv("VAULT_DATABASE_ROLE", "app-role")
    vault_approle_name: str = os.getenv("VAULT_APPROLE_NAME", "app")

    # No hardcoded fallback: the keys must come from the environment or api/.env.
    api_key: str | None = os.getenv("API_KEY")
    admin_api_key: str | None = os.getenv("ADMIN_API_KEY")


settings = Settings()
