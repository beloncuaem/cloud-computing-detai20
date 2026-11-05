"""Verify the app's AppRole only has the capabilities it needs.

Run inside the API container after the stack is up:
    docker compose exec -T api python scripts/check_approle_privileges.py

Exit code 0 means every forbidden capability is absent and every required
capability is present. Exit code 1 prints the exact failures for T06 evidence.
"""
from __future__ import annotations

import sys

import hvac

from app.config import settings
from app.services.vault_client import get_vault_client

FORBIDDEN = {
    f"{settings.vault_transit_mount}/keys/{settings.vault_transit_key}/rotate": {"update"},
    f"{settings.vault_transit_mount}/keys/{settings.vault_transit_key}": {"read", "list"},
    f"{settings.vault_transit_mount}/export/{settings.vault_transit_key}": {"read", "list"},
    f"{settings.vault_transit_mount}/export/encryption-key/{settings.vault_transit_key}": {"read", "list"},
    f"{settings.vault_transit_mount}/keys/{settings.vault_transit_key}/config": {"read", "update"},
}

ALLOWED = {
    f"{settings.vault_transit_mount}/datakey/plaintext/{settings.vault_transit_key}": {"update"},
    f"{settings.vault_transit_mount}/decrypt/{settings.vault_transit_key}": {"update"},
    f"{settings.vault_transit_mount}/rewrap/{settings.vault_transit_key}": {"update"},
    f"{settings.vault_database_mount}/creds/{settings.vault_database_role}": {"read"},
}


def capabilities(client: hvac.Client, path: str) -> set[str] | None:
    try:
        response = client.adapter.post("/v1/sys/capabilities-self", json={"path": path})
        # hvac 2.x returns a dict here; older releases returned a response object.
        payload = response if isinstance(response, dict) else response.json()
        data = payload.get("data", {})
        caps = data.get(path) or data.get("capabilities") or []
        return set(caps)
    except Exception as exc:  # Network/403/unsupported response: cannot verify.
        print(f"ERROR cannot read capabilities for {path}: {type(exc).__name__}")
        return None


def main() -> int:
    # Reuse the workload token. Logging in here would spend the single-use SecretID.
    client = get_vault_client()

    # Do not revoke the token: it is the workload's only login from a one-use SecretID.
    failures: list[str] = []
    print("Forbidden capabilities (application must NOT have these):")
    for path, forbidden in FORBIDDEN.items():
        caps = capabilities(client, path)
        if caps is None:
            failures.append(f"could not verify forbidden path {path}")
            print(f"ERROR {path}: not verifiable")
            continue
        bad = sorted(caps & forbidden)
        if bad:
            failures.append(f"{path} has {bad}")
            print(f"FAIL  {path}: {sorted(caps)}")
        else:
            print(f"PASS  {path}: {sorted(caps)}")

    print("\nRequired capabilities (application must have these):")
    for path, required in ALLOWED.items():
        caps = capabilities(client, path)
        if caps is None:
            failures.append(f"could not verify required path {path}")
            print(f"ERROR {path}: not verifiable")
            continue
        if required & caps:
            print(f"PASS  {path}: {sorted(caps)}")
        else:
            failures.append(f"{path} is missing one of {sorted(required)}")
            print(f"FAIL  {path}: {sorted(caps)}")

    if failures:
        print("\nFAIL: AppRole policy violates least privilege or is incomplete.")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nPASS: AppRole policy matches the least-privilege expectations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
