"""Show that the workload AppRole receives 403 when it tries to rotate the KEK.

    docker compose exec -T api python scripts/prove_rotate_forbidden.py
"""
from __future__ import annotations

import sys

from hvac.exceptions import Forbidden

from app.config import settings
from app.services.vault_client import get_vault_client


def main() -> int:
    client = get_vault_client()
    try:
        client.secrets.transit.rotate_key(
            name=settings.vault_transit_key,
            mount_point=settings.vault_transit_mount,
        )
    except Forbidden:
        print("PASS: workload AppRole cannot rotate the KEK (403)")
        return 0
    print("FAIL: workload AppRole rotated the KEK")
    return 1


if __name__ == "__main__":
    sys.exit(main())
