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
APPROLE_NAME = os.getenv("VAULT_APPROLE_NAME", "app")
APPROLE_POLICY = os.getenv("VAULT_APPROLE_POLICY", f"{APPROLE_NAME}-policy")
APPROLE_OUTPUT_FILE = Path(os.getenv("VAULT_APPROLE_FILE", "./vault-credentials.json"))
# One delivery, ten minutes. A second login with the same SecretID is rejected.
APP_SECRET_ID_TTL = os.getenv("APP_SECRET_ID_TTL", "10m")
APP_SECRET_ID_NUM_USES = int(os.getenv("APP_SECRET_ID_NUM_USES", "1"))
OPERATOR_NAME = os.getenv("VAULT_OPERATOR_APPROLE_NAME", "operator")
OPERATOR_POLICY = os.getenv("VAULT_OPERATOR_POLICY", f"{OPERATOR_NAME}-policy")
OPERATOR_OUTPUT_FILE = Path(os.getenv("VAULT_OPERATOR_FILE", "./operator-credentials.json"))
OPERATOR_SECRET_ID_TTL = os.getenv("OPERATOR_SECRET_ID_TTL", "1h")
OPERATOR_SECRET_ID_NUM_USES = int(os.getenv("OPERATOR_SECRET_ID_NUM_USES", "1"))
DB_ADMIN_USER = os.getenv("VAULT_DB_ADMIN_USER", "vault_admin")
DB_ADMIN_PASSWORD = os.getenv("VAULT_DB_ADMIN_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "encryption_db")

# Workload identity: mint and unwrap data keys, and rewrap them after the
# operator rotates the KEK. It cannot rotate, export, read key metadata, or
# change min_decryption_version.
APP_POLICY = f'''path "{TRANSIT_MOUNT}/datakey/plaintext/{TRANSIT_KEY}" {{
  capabilities = ["update"]
}}
path "{TRANSIT_MOUNT}/decrypt/{TRANSIT_KEY}" {{
  capabilities = ["update"]
}}
path "{TRANSIT_MOUNT}/rewrap/{TRANSIT_KEY}" {{
  capabilities = ["update"]
}}
path "{DATABASE_MOUNT}/creds/{DATABASE_ROLE}" {{
  capabilities = ["read"]
}}
'''

# Operator identity: key lifecycle only. This credential is not mounted into the API.
OPERATOR_POLICY_HCL = f'''path "{TRANSIT_MOUNT}/keys/{TRANSIT_KEY}" {{
  capabilities = ["read"]
}}
path "{TRANSIT_MOUNT}/keys/{TRANSIT_KEY}/rotate" {{
  capabilities = ["update"]
}}
path "{TRANSIT_MOUNT}/keys/{TRANSIT_KEY}/config" {{
  capabilities = ["read", "update"]
}}
path "{TRANSIT_MOUNT}/rewrap/{TRANSIT_KEY}" {{
  capabilities = ["update"]
}}
path "auth/approle/role/{APPROLE_NAME}/secret-id" {{
  capabilities = ["update"]
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


def _enable_approle(client: hvac.Client) -> None:
    auth_response = client.sys.list_auth_methods()
    auth_methods = auth_response.get("data", auth_response)
    if "approle/" not in auth_methods:
        client.sys.enable_auth_method(method_type="approle", path="approle")


def _write_secret_file(path: Path, role_id: str, secret_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"role_id": role_id, "secret_id": secret_id}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _issue_secret(client: hvac.Client, role_name: str) -> tuple[str, str]:
    # secret_id_ttl / secret_id_num_uses are role-level properties, already set by
    # create_or_update_approle(). The secret-id endpoint does not accept them.
    role_id = client.auth.approle.read_role_id(role_name=role_name, mount_point="approle")["data"]["role_id"]
    secret = client.auth.approle.generate_secret_id(
        role_name=role_name,
        mount_point="approle",
    )["data"]["secret_id"]
    return role_id, secret


def configure_approle(client: hvac.Client) -> None:
    client.sys.create_or_update_policy(name=APPROLE_POLICY, policy=APP_POLICY)
    client.sys.create_or_update_policy(name=OPERATOR_POLICY, policy=OPERATOR_POLICY_HCL)
    # Drop the previous overly broad policy if this Vault still has it.
    try:
        client.sys.delete_policy("student2-app-policy")
    except Exception:
        pass
    _enable_approle(client)
    if APPROLE_NAME != "student2-app":
        try:
            client.auth.approle.delete_role(role_name="student2-app", mount_point="approle")
        except Exception:
            pass

    client.auth.approle.create_or_update_approle(
        role_name=APPROLE_NAME,
        token_policies=[APPROLE_POLICY],
        token_ttl="1h",
        token_max_ttl="24h",
        secret_id_ttl=APP_SECRET_ID_TTL,
        secret_id_num_uses=APP_SECRET_ID_NUM_USES,
        bind_secret_id=True,
        mount_point="approle",
    )
    role_id, secret_id = _issue_secret(client, APPROLE_NAME)
    _write_secret_file(APPROLE_OUTPUT_FILE, role_id, secret_id)
    print(
        f"Wrote workload AppRole to {APPROLE_OUTPUT_FILE} "
        f"(secret_id_ttl={APP_SECRET_ID_TTL}, secret_id_num_uses={APP_SECRET_ID_NUM_USES})."
    )

    client.auth.approle.create_or_update_approle(
        role_name=OPERATOR_NAME,
        token_policies=[OPERATOR_POLICY],
        token_ttl="1h",
        token_max_ttl="4h",
        secret_id_ttl=OPERATOR_SECRET_ID_TTL,
        secret_id_num_uses=OPERATOR_SECRET_ID_NUM_USES,
        bind_secret_id=True,
        mount_point="approle",
    )
    operator_role_id, operator_secret_id = _issue_secret(client, OPERATOR_NAME)
    _write_secret_file(OPERATOR_OUTPUT_FILE, operator_role_id, operator_secret_id)
    print(
        f"Wrote operator AppRole to {OPERATOR_OUTPUT_FILE}. "
        "Do not mount this file into the API container."
    )


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
