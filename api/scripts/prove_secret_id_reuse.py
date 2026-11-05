"""Show that a workload SecretID cannot be used twice.

The first login is performed by the workload client and the token is kept.
This script then presents the same SecretID again and expects Vault to reject it.

    docker compose exec -T api python scripts/prove_secret_id_reuse.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import hvac
from hvac.exceptions import VaultError

from app.config import settings
from app.services.vault_client import get_vault_client


def main() -> int:
    get_vault_client()
    data = json.loads(Path(settings.vault_approle_file).read_text(encoding="utf-8"))
    role_id = data.get("role_id")
    secret_id = data.get("secret_id")
    if not role_id or not secret_id:
        print("FAIL: credential file has no role_id or secret_id")
        return 1

    client = hvac.Client(url=settings.vault_addr, timeout=10)
    try:
        client.auth.approle.login(role_id=role_id, secret_id=secret_id, mount_point="approle")
    except VaultError as exc:
        print(f"PASS: reused SecretID was rejected ({type(exc).__name__})")
        return 0
    print("FAIL: Vault accepted a SecretID that had already been used")
    return 1


if __name__ == "__main__":
    sys.exit(main())
