"""Rewrap every stored DEK onto the latest KEK version.

This does not decrypt application payloads. Vault Transit rewraps the DEK
ciphertext in place; the API then stores the new `vault:vN:` prefix and
`kek_version`. Run inside the API container, whose AppRole may rewrap but
may not rotate the key:

    docker compose exec -T api python scripts/rewrap_dek.py
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import DatabaseManager
from app.models import AuditEvent, SensitiveRecord
from app.services.encryption import kek_version_from_ciphertext
from app.services.vault_client import get_vault_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    client = get_vault_client()
    manager = DatabaseManager()
    manager.initialize()
    engine = manager.get_engine()
    successful = 0
    failed = 0
    try:
        with engine.connect() as connection:
            ids = list(connection.execute(select(SensitiveRecord.id)).scalars())
        for record_id in ids:
            try:
                with Session(engine, expire_on_commit=False) as session:
                    with session.begin():
                        record = session.get(SensitiveRecord, record_id, with_for_update=True)
                        if record is None:
                            continue
                        response = client.secrets.transit.rewrap_data(
                            name=record.kek_name or settings.vault_transit_key,
                            ciphertext=record.encrypted_dek,
                            mount_point=settings.vault_transit_mount,
                        )
                        wrapped = response["data"]["ciphertext"]
                        version = kek_version_from_ciphertext(wrapped)
                        if version is None:
                            raise RuntimeError("Rewrapped DEK is missing a vault:vN: prefix")
                        previous = record.kek_version
                        record.encrypted_dek = wrapped
                        record.kek_version = version
                        record.kek_name = record.kek_name or settings.vault_transit_key
                        session.add(
                            AuditEvent(
                                event_type="dek.rewrap",
                                outcome="success",
                                record_id=record.id,
                                details=json.dumps(
                                    {"from_version": previous, "to_version": version}
                                ),
                            )
                        )
                successful += 1
                logger.info("Rewrapped DEK for record %s", record_id)
            except Exception:
                failed += 1
                logger.exception("Could not rewrap DEK for record %s; original row was retained", record_id)
        logger.info(
            "DEK rewrap finished: successful=%s failed=%s total=%s",
            successful,
            failed,
            len(ids),
        )
        if failed:
            raise SystemExit(1)
    finally:
        manager.shutdown()


if __name__ == "__main__":
    main()
