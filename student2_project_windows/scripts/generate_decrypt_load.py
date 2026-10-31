"""Generate a burst of Transit decrypt requests for the anomaly-alert test.

Run this with a token that is NOT the application's AppRole, so the audit log
has a separate identity for the attack burst. The vault-init service already
has VAULT_DEMO_TOKEN=root in the fallback stack:

    docker compose run --rm --no-deps vault-init \
        python scripts/generate_decrypt_load.py --count 200

Never use this against a real environment. It is a lab-only load generator.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import hvac

from app.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=200, help="number of decrypt calls")
    parser.add_argument("--key", default=settings.vault_transit_key)
    parser.add_argument("--mount", default=settings.vault_transit_mount)
    args = parser.parse_args()

    token = os.getenv("VAULT_DEMO_TOKEN") or os.getenv("VAULT_SETUP_TOKEN")
    if not token:
        print(
            "Set VAULT_DEMO_TOKEN to a dedicated demo token. Do not use the app AppRole "
            "for this test because the audit identity must be separate.",
            file=sys.stderr,
        )
        return 1

    client = hvac.Client(url=settings.vault_addr, token=token, timeout=10)
    if not client.is_authenticated():
        print("Vault token is not authenticated", file=sys.stderr)
        return 1

    response = client.secrets.transit.generate_data_key(
        name=args.key,
        key_type="plaintext",
        bits=256,
        mount_point=args.mount,
    )
    ciphertext = response["data"]["ciphertext"]

    started = time.monotonic()
    for _ in range(args.count):
        client.secrets.transit.decrypt_data(
            name=args.key,
            ciphertext=ciphertext,
            mount_point=args.mount,
        )
    elapsed = time.monotonic() - started
    rate = args.count / elapsed * 60 if elapsed else float("inf")
    print(
        f"Generated {args.count} decrypt requests in {elapsed:.2f}s "
        f"(~{rate:.0f} requests/minute) using the demo token identity."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
