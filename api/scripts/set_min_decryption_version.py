"""Block decryption of retired KEK versions. Operator identity only.

Run after every stored DEK has been rewrapped onto the new version:

    docker compose run --rm --no-deps --entrypoint python vault-init scripts/set_min_decryption_version.py 2
"""
from __future__ import annotations

import sys

from app.config import settings
from app.services.vault_client import get_operator_client


def main() -> None:
    version = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    if version < 1:
        raise SystemExit("min_decryption_version must be >= 1")
    client = get_operator_client()
    client.secrets.transit.update_key_configuration(
        name=settings.vault_transit_key,
        min_decryption_version=version,
        mount_point=settings.vault_transit_mount,
    )
    print(
        f"Operator set min_decryption_version={version} on '{settings.vault_transit_key}'. "
        "Ciphertext from older versions will be rejected."
    )


if __name__ == "__main__":
    main()
