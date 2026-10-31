"""Rotate the Vault Transit KEK version without re-encrypting application payloads."""
from __future__ import annotations

from app.config import settings
from app.services.vault_client import get_vault_client


def main() -> None:
    client = get_vault_client()
    client.secrets.transit.rotate_key(
        name=settings.vault_transit_key,
        mount_point=settings.vault_transit_mount,
    )
    print(
        f"Rotated Transit KEK '{settings.vault_transit_key}'. Existing wrapped DEKs remain encrypted "
        "with older versions until you optionally rewrap them."
    )


if __name__ == "__main__":
    main()
