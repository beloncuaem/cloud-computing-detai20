"""Record APIs: plaintext is only accepted/returned at the application boundary."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuditEvent, SensitiveRecord
from app.schemas import RecordCreate, RecordCreated, RecordMetadata, RecordRead
from app.security import require_api_key
from app.services.encryption import decrypt_sensitive_value, encrypt_sensitive_value
from app.services.vault_client import get_vault_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/records", tags=["Records"], dependencies=[Depends(require_api_key)])


def _audit(
    db: Session,
    *,
    event_type: str,
    outcome: str,
    record_id: uuid.UUID | None = None,
    details: dict[str, object] | None = None,
) -> None:
    # Never write plaintext, ciphertext, DEKs, tokens, or credentials into audit logs.
    db.add(
        AuditEvent(
            event_type=event_type,
            outcome=outcome,
            record_id=record_id,
            details=json.dumps(details or {}, ensure_ascii=False),
        )
    )


@router.post("", response_model=RecordCreated, status_code=status.HTTP_201_CREATED)
def create_record(payload: RecordCreate, db: Session = Depends(get_db)) -> RecordCreated:
    record_id = uuid.uuid4()
    try:
        client = get_vault_client()
        encrypted = encrypt_sensitive_value(
            client, payload.value, record_id=record_id, record_type=payload.record_type
        )
    except Exception as exc:
        logger.exception("Envelope encryption failed; request data was not logged")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Encryption service is unavailable",
        ) from exc

    row = SensitiveRecord(
        id=record_id,
        record_type=payload.record_type,
        ciphertext=encrypted.ciphertext,
        nonce=encrypted.nonce,
        encrypted_dek=encrypted.encrypted_dek,
        kek_name=encrypted.kek_name,
        kek_version=encrypted.kek_version,
    )
    db.add(row)
    _audit(
        db,
        event_type="record.create",
        outcome="success",
        record_id=record_id,
        details={"record_type": payload.record_type, "encryption": "AES-256-GCM"},
    )
    try:
        db.commit()
        db.refresh(row)
    except Exception as exc:
        db.rollback()
        logger.exception("Database insert failed")
        raise HTTPException(status_code=503, detail="Could not store encrypted record") from exc

    return RecordCreated(
        id=row.id,
        record_type=row.record_type,
        status="encrypted_and_stored",
        created_at=row.created_at or datetime.now(timezone.utc),
    )


@router.get("", response_model=list[RecordMetadata])
def list_records(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[RecordMetadata]:
    rows = db.scalars(
        select(SensitiveRecord).order_by(SensitiveRecord.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return [
        RecordMetadata(
            id=row.id,
            record_type=row.record_type,
            ciphertext_bytes=len(row.ciphertext),
            kek_name=row.kek_name,
            kek_version=row.kek_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.get("/{record_id}/metadata", response_model=RecordMetadata)
def get_record_metadata(record_id: uuid.UUID, db: Session = Depends(get_db)) -> RecordMetadata:
    row = db.get(SensitiveRecord, record_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return RecordMetadata(
        id=row.id,
        record_type=row.record_type,
        ciphertext_bytes=len(row.ciphertext),
        kek_name=row.kek_name,
        kek_version=row.kek_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/{record_id}", response_model=RecordRead)
def read_record(record_id: uuid.UUID, db: Session = Depends(get_db)) -> RecordRead:
    row = db.get(SensitiveRecord, record_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")
    try:
        value = decrypt_sensitive_value(
            get_vault_client(),
            ciphertext=row.ciphertext,
            nonce=row.nonce,
            encrypted_dek=row.encrypted_dek,
            kek_name=row.kek_name,
            record_id=row.id,
            record_type=row.record_type,
        )
    except Exception as exc:
        logger.exception("Decryption failed for record ID %s", record_id)
        _audit(
            db,
            event_type="record.read",
            outcome="failure",
            record_id=record_id,
            details={"reason": "decrypt_failed"},
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not decrypt this record; check Vault access and key availability",
        ) from exc

    _audit(
        db,
        event_type="record.read",
        outcome="success",
        record_id=record_id,
        details={"operation": "decrypt"},
    )
    db.commit()
    return RecordRead(
        id=row.id,
        record_type=row.record_type,
        value=value,
        created_at=row.created_at,
    )
