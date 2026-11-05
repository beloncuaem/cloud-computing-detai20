"""Print and check the workload AppRole SecretID limits. Setup token only.

Run from the vault-init container, which has the lab setup token:

    docker compose run --rm --no-deps --entrypoint python vault-init scripts/show_approle_lifecycle.py

Exit 0 only when secret_id_ttl is 10 minutes and secret_id_num_uses is 1.
"""
from __future__ import annotations

import os
import sys

import hvac

from app.config import settings

EXPECTED_TTL_SECONDS = 600
EXPECTED_NUM_USES = 1


def main() -> int:
    token = os.getenv("VAULT_SETUP_TOKEN", "")
    if not token:
        print("FAIL: VAULT_SETUP_TOKEN is not set. Run this from vault-init.")
        return 1
    client = hvac.Client(url=settings.vault_addr, token=token, timeout=10)
    if not client.is_authenticated():
        print(f"FAIL: setup token was rejected by Vault at {settings.vault_addr}")
        return 1

    role = client.auth.approle.read_role(
        role_name=settings.vault_approle_name,
        mount_point="approle",
    )["data"]
    ttl = role.get("secret_id_ttl")
    uses = role.get("secret_id_num_uses")
    policies = role.get("token_policies")
    print(f"role={settings.vault_approle_name}")
    print(f"secret_id_ttl={ttl}")
    print(f"secret_id_num_uses={uses}")
    print(f"secret_id_bound_cidrs={role.get('secret_id_bound_cidrs')}")
    print(f"token_policies={policies}")
    print(f"token_ttl={role.get('token_ttl')}")

    ttl_ok = ttl in {EXPECTED_TTL_SECONDS, str(EXPECTED_TTL_SECONDS)}
    uses_ok = uses in {EXPECTED_NUM_USES, str(EXPECTED_NUM_USES)}
    if ttl_ok and uses_ok:
        print("PASS: SecretID expires in 10 minutes and can be used once.")
        return 0
    print(
        "FAIL: expected secret_id_ttl=600 and secret_id_num_uses=1 "
        f"(got ttl={ttl}, uses={uses})."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
