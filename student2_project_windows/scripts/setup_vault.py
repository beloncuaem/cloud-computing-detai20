"""Configure Vault Transit, DB secrets, and AppRole against local Windows services.

Run only in a disposable classroom lab. It expects Vault already running and initialized,
for example with `vault server -dev -dev-root-token-id=root`.
"""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import hvac
from dotenv import load_dotenv

load_dotenv()
VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200").rstrip("/")
VAULT_TOKEN = os.getenv("VAULT_SETUP_TOKEN", "")
TRANSIT_MOUNT = os.getenv("VAULT_TRANSIT_MOUNT", "transit")
TRANSIT_KEY = os.getenv("VAULT_TRANSIT_KEY", "app-data-key")
DATABASE_MOUNT = os.getenv("VAULT_DATABASE_MOUNT", "database")
DATABASE_CONNECTION = os.getenv("VAULT_DATABASE_CONNECTION", "postgres")
DATABASE_ROLE = os.getenv("VAULT_DATABASE_ROLE", "app-role")
APPROLE_NAME = os.getenv("VAULT_APPROLE_NAME", "student2-app")
APPROLE_OUTPUT_FILE = Path(os.getenv("VAULT_APPROLE_FILE", "./vault-credentials.json"))
DB_ADMIN_USER = os.getenv("VAULT_DB_ADMIN_USER", "vault_admin")
DB_ADMIN_PASSWORD = os.getenv("VAULT_DB_ADMIN_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "encryption_db")

APP_POLICY = f'''path "{TRANSIT_MOUNT}/datakey/plaintext/{TRANSIT_KEY}" {{
  capabilities = ["update"]
}}
path "{TRANSIT_MOUNT}/decrypt/{TRANSIT_KEY}" {{
  capabilities = ["update"]
}}
path "{TRANSIT_MOUNT}/keys/{TRANSIT_KEY}" {{
  capabilities = ["read"]
}}
path "{TRANSIT_MOUNT}/keys/{TRANSIT_KEY}/rotate" {{
  capabilities = ["update"]
}}
path "{DATABASE_MOUNT}/creds/{DATABASE_ROLE}" {{
  capabilities = ["read"]
}}
'''


def ensure_mount(client: hvac.Client, path: str, backend_type: str) -> None:
    response = client.sys.list_mounted_secrets_engines()
    mounts = response.get("data", response)
    if f"{path.rstrip('/')}/" not in mounts:
        client.sys.enable_secrets_engine(backend_type=backend_type, path=path)
        print(f"Enabled Vault secrets engine: {path}/")


def ensure_transit_key(client: hvac.Client) -> None:
    try:
        client.secrets.transit.read_key(name=TRANSIT_KEY, mount_point=TRANSIT_MOUNT)
    except hvac.exceptions.InvalidPath:
        client.secrets.transit.create_key(
            name=TRANSIT_KEY,
            key_type="aes256-gcm96",
            mount_point=TRANSIT_MOUNT,
        )
        print(f"Created Transit key: {TRANSIT_KEY}")


def configure_database_engine(client: hvac.Client) -> None:
    if not DB_ADMIN_PASSWORD:
        raise RuntimeError("Set VAULT_DB_ADMIN_PASSWORD in .env")
    # Vault itself runs on the host, so localhost/127.0.0.1 points to Windows PostgreSQL.
    connection_url = (
        f"postgresql://{{{{username}}}}:{{{{password}}}}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=disable"
    )
    client.secrets.database.configure(
        name=DATABASE_CONNECTION,
        plugin_name="postgresql-database-plugin",
        allowed_roles=[DATABASE_ROLE],
        connection_url=connection_url,
        username=DB_ADMIN_USER,
        password=DB_ADMIN_PASSWORD,
        mount_point=DATABASE_MOUNT,
    )
    creation_statements = [
        'CREATE ROLE "{{name}}" WITH LOGIN PASSWORD \'{{password}}\' VALID UNTIL \'{{expiration}}\';',
        f'GRANT CONNECT ON DATABASE {DB_NAME} TO "{{{{name}}}}";',
        'GRANT USAGE ON SCHEMA public TO "{{name}}";',
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE sensitive_records TO "{{name}}";',
        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE audit_events TO "{{name}}";',
        'GRANT USAGE, SELECT ON SEQUENCE audit_events_id_seq TO "{{name}}";',
    ]
    client.secrets.database.create_role(
        name=DATABASE_ROLE,
        db_name=DATABASE_CONNECTION,
        creation_statements=creation_statements,
        default_ttl="1h",
        max_ttl="24h",
        mount_point=DATABASE_MOUNT,
    )
    print("Configured Vault Database Secrets Engine for local PostgreSQL.")


def configure_approle(client: hvac.Client) -> None:
    client.sys.create_or_update_policy(name="student2-app-policy", policy=APP_POLICY)
    auth_response = client.sys.list_auth_methods()
    auth_methods = auth_response.get("data", auth_response)
    if "approle/" not in auth_methods:
        client.sys.enable_auth_method(method_type="approle", path="approle")
    client.auth.approle.create_or_update_approle(
        role_name=APPROLE_NAME,
        token_policies=["student2-app-policy"],
        token_ttl="1h",
        token_max_ttl="24h",
        secret_id_ttl="0s",
        secret_id_num_uses=0,
        bind_secret_id=True,
        mount_point="approle",
    )
    role_id = client.auth.approle.read_role_id(
        role_name=APPROLE_NAME, mount_point="approle"
    )["data"]["role_id"]
    secret_id = client.auth.approle.generate_secret_id(
        role_name=APPROLE_NAME, mount_point="approle"
    )["data"]["secret_id"]
    APPROLE_OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    APPROLE_OUTPUT_FILE.write_text(
        json.dumps({"role_id": role_id, "secret_id": secret_id}, indent=2),
        encoding="utf-8",
    )
    try:
        APPROLE_OUTPUT_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    print(f"Wrote AppRole credentials to {APPROLE_OUTPUT_FILE}. Keep this file private.")


def main() -> None:
    if not VAULT_TOKEN:
        raise SystemExit("Set VAULT_SETUP_TOKEN in .env; for the local dev server it may be 'root'.")
    client = hvac.Client(url=VAULT_ADDR, token=VAULT_TOKEN, timeout=10)
    if not client.is_authenticated():
        raise SystemExit(f"Cannot authenticate to Vault at {VAULT_ADDR}; check that Vault is running and token is correct.")
    ensure_mount(client, TRANSIT_MOUNT, "transit")
    ensure_transit_key(client)
    ensure_mount(client, DATABASE_MOUNT, "database")
    configure_database_engine(client)
    configure_approle(client)
    print("Vault setup completed. The API uses AppRole credentials, not the setup/root token.")


if __name__ == "__main__":
    main()
