"""Rotate the Transit KEK with the operator identity.

The workload AppRole cannot call this path. Run from vault-init, which has the
operator credential file and does not share it with the API container:

    docker compose run --rm --no-deps --entrypoint python vault-init scripts/rotate_transit_key.py

Rotating creates a new KEK version. Existing DEKs stay on the old version until
`scripts/rewrap_dek.py` runs.
"""
from __future__ import annotations

from app.config import settings
from app.services.vault_client import get_operator_client


def main() -> None:
    client = get_operator_client()
    client.secrets.transit.rotate_key(
        name=settings.vault_transit_key,
        mount_point=settings.vault_transit_mount,
    )
    print(
        f"Operator rotated Transit KEK '{settings.vault_transit_key}'. "
        "Existing wrapped DEKs stay on the previous version until rewrap_dek.py runs."
    )


if __name__ == "__main__":
    main()
