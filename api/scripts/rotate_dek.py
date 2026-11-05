"""Re-encrypt all stored records with newly generated DEKs.

Run from the project root with the local Python environment: `python scripts/rotate_dek.py`.
Each record is committed independently; a failure leaves that record unchanged.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from app.database import DatabaseManager
from app.models import AuditEvent, SensitiveRecord
from app.services.encryption import decrypt_sensitive_value, encrypt_sensitive_value
from app.services.vault_client import get_vault_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    client = get_vault_client()
    manager = DatabaseManager()
    manager.initialize()
    engine = manager.get_engine()
    try:
        with engine.connect() as connection:
            ids = list(connection.execute(select(SensitiveRecord.id)).scalars())
        successful = 0
        failed = 0
        for record_id in ids:
            try:
                # A separate transaction per record avoids leaving a partly-updated batch.
                from sqlalchemy.orm import Session
                with Session(engine, expire_on_commit=False) as session:
                    with session.begin():
                        record = session.get(SensitiveRecord, record_id, with_for_update=True)
                        if record is None:
                            continue
                        plaintext = decrypt_sensitive_value(
                            client,
                            ciphertext=record.ciphertext,
                            nonce=record.nonce,
                            encrypted_dek=record.encrypted_dek,
                            kek_name=record.kek_name,
                            record_id=record.id,
                            record_type=record.record_type,
                        )
                        new_payload = encrypt_sensitive_value(
                            client,
                            plaintext,
                            record_id=record.id,
                            record_type=record.record_type,
                        )
                        record.ciphertext = new_payload.ciphertext
                        record.nonce = new_payload.nonce
                        record.encrypted_dek = new_payload.encrypted_dek
                        record.kek_name = new_payload.kek_name
                        record.kek_version = new_payload.kek_version
                        session.add(
                            AuditEvent(
                                event_type="dek.rotate",
                                outcome="success",
                                record_id=record.id,
                                details='{"method":"new_dek_and_reencrypt"}',
                            )
                        )
                successful += 1
                logger.info("Rotated DEK for record %s", record_id)
            except Exception:
                failed += 1
                logger.exception("Could not rotate DEK for record %s; original row was retained", record_id)
        logger.info("DEK rotation finished: successful=%s failed=%s total=%s", successful, failed, len(ids))
        if failed:
            raise SystemExit(1)
    finally:
        manager.shutdown()


if __name__ == "__main__":
    main()
