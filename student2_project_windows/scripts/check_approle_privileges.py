"""Verify the app's AppRole only has the capabilities it needs.

Run inside the API container after the stack is up:
    docker compose exec -T api python scripts/check_approle_privileges.py

Exit code 0 means every forbidden capability is absent and every required
capability is present. Exit code 1 prints the exact failures for T06 evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import hvac

from app.config import settings

FORBIDDEN = {
    f"{settings.vault_transit_mount}/keys/{settings.vault_transit_key}/rotate": {"update"},
    f"{settings.vault_transit_mount}/keys/{settings.vault_transit_key}": {"read", "list"},
    f"{settings.vault_transit_mount}/export/{settings.vault_transit_key}": {"read", "list"},
    f"{settings.vault_transit_mount}/keys/{settings.vault_transit_key}/config": {"read", "update"},
}

ALLOWED = {
    f"{settings.vault_transit_mount}/datakey/plaintext/{settings.vault_transit_key}": {"update"},
    f"{settings.vault_transit_mount}/decrypt/{settings.vault_transit_key}": {"update"},
    f"{settings.vault_database_mount}/creds/{settings.vault_database_role}": {"read"},
}


def read_credentials() -> tuple[str, str]:
    path = Path(settings.vault_approle_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    role_id = data.get("role_id")
    secret_id = data.get("secret_id")
    if not role_id or not secret_id:
        raise RuntimeError("AppRole file is missing role_id or secret_id")
    return role_id, secret_id


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
    role_id, secret_id = read_credentials()
    client = hvac.Client(url=settings.vault_addr, timeout=10)
    client.auth.approle.login(role_id=role_id, secret_id=secret_id, mount_point="approle")

    failures: list[str] = []
    try:
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
    finally:
        try:
            client.auth.token.revoke_self()
        except Exception:
            pass

    if failures:
        print("\nFAIL: AppRole policy violates least privilege or is incomplete.")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nPASS: AppRole policy matches the least-privilege expectations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
