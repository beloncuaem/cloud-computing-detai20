"""FastAPI entry point for the Student 2 project."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.database import manager
from app.routes.admin import router as admin_router
from app.routes.records import router as records_router
from app.services.vault_client import get_vault_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def _automatic_db_rotation_loop() -> None:
    """Refresh dynamic credentials before their 1-hour demo lease expires."""
    while True:
        await asyncio.sleep(settings.db_rotation_interval_seconds)
        try:
            result = await asyncio.to_thread(manager.rotate_database_credentials)
            logger.info(
                "Automatic DB credential rotation completed; new lease duration=%s seconds",
                result.get("new_lease_duration_seconds"),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            # Retry soon rather than wait for the full interval if a rotation fails.
            logger.exception("Automatic database credential rotation failed; retrying in 30 seconds")
            await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager.initialize()
    app.state.rotation_task = None
    if settings.use_vault_db_creds:
        app.state.rotation_task = asyncio.create_task(_automatic_db_rotation_loop())
    logger.info("Application startup completed")
    try:
        yield
    finally:
        task = app.state.rotation_task
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        manager.shutdown()


app = FastAPI(
    title="Student 2 - Envelope Encryption API",
    description=(
        "Demo API for PostgreSQL, Vault Transit envelope encryption, AppRole authentication, "
        "dynamic database credentials, and rotation experiments."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(records_router)
app.include_router(admin_router)


@app.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["Health"])
def ready() -> dict[str, str]:
    try:
        with manager.get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        if not get_vault_client().is_authenticated():
            raise RuntimeError("Vault AppRole token is not authenticated")
    except Exception as exc:
        logger.warning("Readiness check failed (%s)", type(exc).__name__)
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="A required dependency is not ready") from exc
    return {"status": "ready", "database": "ok", "vault": "authenticated"}
