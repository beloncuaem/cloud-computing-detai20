"""Database engine management, including overlap-based credential rotation."""
from __future__ import annotations

import logging
import threading
from typing import Generator

from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.services.vault_client import get_vault_client

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._rotation_lock = threading.Lock()
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None
        self._lease_id: str | None = None
        self._lease_duration: int | None = None

    @property
    def is_dynamic(self) -> bool:
        return settings.use_vault_db_creds

    def initialize(self) -> None:
        with self._lock:
            if self._engine is not None:
                return
            if settings.use_vault_db_creds:
                engine, lease_id, lease_duration = self._create_engine_from_vault()
            else:
                engine = create_engine(
                    settings.database_url,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10,
                )
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                lease_id, lease_duration = None, None
            self._engine = engine
            self._session_factory = sessionmaker(
                bind=engine, class_=Session, autoflush=False, expire_on_commit=False
            )
            self._lease_id = lease_id
            self._lease_duration = lease_duration
        logger.info("Database connection initialized (Vault dynamic credentials=%s)", settings.use_vault_db_creds)

    def _create_engine_from_vault(self) -> tuple[Engine, str | None, int | None]:
        client = get_vault_client()
        response = client.secrets.database.generate_credentials(
            name=settings.vault_database_role,
            mount_point=settings.vault_database_mount,
        )
        data = response["data"]
        url = URL.create(
            drivername="postgresql+psycopg",
            username=data["username"],
            password=data["password"],
            host=settings.db_host,
            port=settings.db_port,
            database=settings.db_name,
        )
        engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=max(60, int(response.get("lease_duration") or 3600) - 120),
        )
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            engine.dispose()
            # Do not log the URL: it contains a short-lived username/password.
            logger.exception("Could not verify a newly issued Vault database credential")
            raise
        return engine, response.get("lease_id"), int(response.get("lease_duration") or 3600)

    def get_engine(self) -> Engine:
        with self._lock:
            if self._engine is None:
                raise RuntimeError("DatabaseManager is not initialized")
            return self._engine

    def new_session(self) -> Session:
        with self._lock:
            if self._session_factory is None:
                raise RuntimeError("DatabaseManager is not initialized")
            factory = self._session_factory
        return factory()

    def rotate_database_credentials(self) -> dict[str, int | str | None]:
        """Create/test new credentials and switch new requests to them.

        The previous lease is deliberately not revoked immediately. It remains valid
        during the overlap window so in-flight requests using the previous pool can
        finish; Vault revokes it when its lease expires. This demo runs one Uvicorn
        worker because an in-memory engine swap is process-local.
        """
        if not settings.use_vault_db_creds:
            raise RuntimeError("Database credential rotation requires USE_VAULT_DB_CREDS=true")
        with self._rotation_lock:
            new_engine, new_lease_id, new_lease_duration = self._create_engine_from_vault()
            with self._lock:
                old_engine = self._engine
                old_lease_duration = self._lease_duration
                self._engine = new_engine
                self._session_factory = sessionmaker(
                    bind=new_engine, class_=Session, autoflush=False, expire_on_commit=False
                )
                self._lease_id = new_lease_id
                self._lease_duration = new_lease_duration
            if old_engine is not None:
                # Do not close checked-out connections; old credentials stay valid
                # until their Vault lease expires.
                old_engine.dispose(close=False)
            logger.info("Switched database pool to a fresh Vault-issued credential")
            return {
                "new_lease_duration_seconds": new_lease_duration,
                "previous_lease_duration_seconds": old_lease_duration,
            }

    def shutdown(self) -> None:
        with self._lock:
            engine = self._engine
            self._engine = None
            self._session_factory = None
        if engine is not None:
            engine.dispose()


manager = DatabaseManager()


def get_db() -> Generator[Session, None, None]:
    try:
        session = manager.new_session()
    except RuntimeError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    try:
        yield session
    finally:
        session.close()
