"""Restricted demo endpoints for key and database-credential rotation."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from hvac.exceptions import Forbidden

from app.config import settings
from app.database import manager
from app.security import require_admin_key
from app.services.vault_client import get_vault_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Administration"], dependencies=[Depends(require_admin_key)])


@router.post("/rotation/database")
def rotate_database_credentials() -> dict[str, object]:
    """Issue a new dynamic DB login and switch new requests to a tested connection pool."""
    if not settings.use_vault_db_creds:
        raise HTTPException(
            status_code=409,
            detail="Set USE_VAULT_DB_CREDS=true to use database credential rotation",
        )
    try:
        result = manager.rotate_database_credentials()
    except Exception as exc:
        logger.exception("Database credential rotation failed")
        raise HTTPException(status_code=503, detail="Database credential rotation failed") from exc
    return {
        "status": "rotated",
        "message": "New requests use the new pool; the previous Vault lease is allowed to expire for in-flight work.",
        **result,
    }


@router.post("/rotation/transit-key")
def rotate_transit_key() -> dict[str, str]:
    """Attempt KEK rotation with the workload identity. Vault must deny it."""
    try:
        client = get_vault_client()
        client.secrets.transit.rotate_key(
            name=settings.vault_transit_key,
            mount_point=settings.vault_transit_mount,
        )
    except Forbidden as exc:
        raise HTTPException(
            status_code=403,
            detail="The workload identity cannot rotate the KEK. Use the operator identity.",
        ) from exc
    except Exception as exc:
        logger.exception("Vault Transit key rotation failed")
        raise HTTPException(status_code=503, detail="Vault Transit key rotation failed") from exc
    raise HTTPException(
        status_code=500,
        detail="Workload identity was allowed to rotate the KEK; the AppRole policy is too broad.",
    )
