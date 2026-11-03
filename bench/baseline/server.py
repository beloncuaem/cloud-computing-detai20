"""Plaintext benchmark baseline for H1 (configuration A).

This is a benchmark-only service. It is NOT part of the application and must
never be deployed: it stores the sensitive value as plaintext on purpose so we
can measure the cost of envelope encryption against a comparable DB-backed API.

It mirrors the target API's write/read work:
  POST /records -> INSERT one record row + one audit row in one transaction
  GET /records/{id} -> SELECT row + INSERT one audit row, return plaintext
  GET /ready

Run it in the API image (FastAPI, uvicorn, psycopg are already installed) on
the compose network, for example:

    docker run -d --name detai20-baseline --network detai20_default \
      -p 8001:8001 -v "<repo>/bench/baseline:/baseline:ro" -w /baseline \
      -e BASELINE_DB_DSN="postgresql://postgres:local_demo_postgres_password@postgres:5432/encryption_db" \
      -e API_KEY="local-demo-api-key-change-me" \
      detai20-api:local uvicorn server:app --host 0.0.0.0 --port 8001

Demo credentials only; see docs/infra/local-stack.md. Do not use real data.
"""
from __future__ import annotations

import contextlib
import json
import logging
import os
import queue
import uuid
from typing import Iterator

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger("bench.baseline")
logging.basicConfig(level=logging.INFO)

DB_DSN = os.getenv("BASELINE_DB_DSN", "")
API_KEY = os.getenv("API_KEY", "")
POOL_SIZE = int(os.getenv("BASELINE_POOL_SIZE", "15"))
ADMIN_DSN = os.getenv("BASELINE_ADMIN_DSN", DB_DSN)


class RecordCreate(BaseModel):
    record_type: str
    value: str


class ConnectionPool:
    """Small thread-safe pool; one connection is checked out per request."""

    def __init__(self, dsn: str, size: int) -> None:
        self._dsn = dsn
        self._items: queue.LifoQueue[psycopg.Connection] = queue.LifoQueue()
        for _ in range(size):
            self._items.put(self._connect())

    def _connect(self) -> psycopg.Connection:
        conn = psycopg.connect(self._dsn, connect_timeout=10)
        conn.autocommit = False
        return conn

    @contextlib.contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        conn = self._items.get()
        try:
            if conn.closed:
                conn = self._connect()
            yield conn
        finally:
            # Return the connection in a clean state; a render error or a
            # caller that forgot to commit must not leak a transaction into
            # the next request.
            try:
                if not conn.closed:
                    conn.rollback()
            except Exception:
                with contextlib.suppress(Exception):
                    conn.close()
                conn = self._connect()
            self._items.put(conn)

    def close(self) -> None:
        while not self._items.empty():
            self._items.get_nowait().close()


pool: ConnectionPool | None = None


def create_schema() -> None:
    with psycopg.connect(ADMIN_DSN, connect_timeout=10, autocommit=True) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bench_plaintext_records (
                id UUID PRIMARY KEY,
                record_type VARCHAR(50) NOT NULL,
                value TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bench_plaintext_audit (
                id BIGSERIAL PRIMARY KEY,
                event_type VARCHAR(80) NOT NULL,
                outcome VARCHAR(20) NOT NULL,
                record_id UUID NULL,
                details TEXT NOT NULL DEFAULT '{}',
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    global pool
    if not DB_DSN:
        raise RuntimeError("Set BASELINE_DB_DSN")
    create_schema()
    pool = ConnectionPool(DB_DSN, POOL_SIZE)
    logger.info("Baseline pool ready (size=%s)", POOL_SIZE)
    try:
        yield
    finally:
        if pool is not None:
            pool.close()


app = FastAPI(title="Envelope encryption benchmark baseline", lifespan=lifespan)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


@app.get("/ready")
def ready() -> dict[str, str]:
    if pool is None:
        raise HTTPException(status_code=503, detail="Not ready")
    with pool.connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "ready", "database": "ok", "mode": "plaintext-baseline"}


@app.post("/records", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_record(payload: RecordCreate) -> dict[str, str]:
    record_id = uuid.uuid4()
    assert pool is not None
    with pool.connection() as conn:
        with conn.transaction():
            conn.execute(
                "INSERT INTO bench_plaintext_records (id, record_type, value) VALUES (%s, %s, %s)",
                (record_id, payload.record_type, payload.value),
            )
            conn.execute(
                "INSERT INTO bench_plaintext_audit (event_type, outcome, record_id, details) "
                "VALUES (%s, %s, %s, %s)",
                ("record.create", "success", record_id, json.dumps({"record_type": payload.record_type})),
            )
        # Mirror the target API's post-commit refresh (one extra SELECT).
        row = conn.execute(
            "SELECT created_at FROM bench_plaintext_records WHERE id = %s", (record_id,)
        ).fetchone()
        conn.commit()
    created_at = row[0].isoformat() if row else None
    return {
        "id": str(record_id),
        "record_type": payload.record_type,
        "status": "stored_plaintext",
        "created_at": created_at,
    }


@app.get("/records/{record_id}", dependencies=[Depends(require_api_key)])
def read_record(record_id: uuid.UUID) -> dict[str, str]:
    assert pool is not None
    with pool.connection() as conn:
        with conn.transaction():
            row = conn.execute(
                "SELECT record_type, value FROM bench_plaintext_records WHERE id = %s",
                (record_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Record not found")
            conn.execute(
                "INSERT INTO bench_plaintext_audit (event_type, outcome, record_id, details) "
                "VALUES (%s, %s, %s, %s)",
                ("record.read", "success", record_id, json.dumps({"operation": "plaintext_read"})),
            )
    return {"id": str(record_id), "record_type": row[0], "value": row[1]}
