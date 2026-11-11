"""Issue a fresh one-use workload SecretID. Operator identity only.

Replaces the credential file. Restart the API so it logs in with the new
SecretID; the previous SecretID cannot be reused.

    docker compose run --rm --no-deps --entrypoint python vault-init scripts/issue_workload_secret.py
"""
from __future__ import annotations

import json
from pathlib import Path

from app.config import settings
from app.services.vault_client import get_operator_client


def main() -> None:
    client = get_operator_client()
    # The role already enforces secret_id_ttl=10m and secret_id_num_uses=1;
    # the secret-id endpoint does not accept those parameters.
    secret = client.auth.approle.generate_secret_id(
        role_name=settings.vault_approle_name,
        mount_point="approle",
    )["data"]["secret_id"]
    path = Path(settings.vault_approle_file)
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    role_id = current.get("role_id")
    if not role_id:
        role_id = client.auth.approle.read_role_id(
            role_name=settings.vault_approle_name,
            mount_point="approle",
        )["data"]["role_id"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"role_id": role_id, "secret_id": secret}, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print(
        f"Issued a new one-use SecretID for role '{settings.vault_approle_name}' "
        f"(ttl=10m). Restart the API so it picks up the new file."
    )


if __name__ == "__main__":
    main()
