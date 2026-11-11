-- Run this while connected to encryption_db as a database administrator.
-- In Docker, db/init/01-init.sh runs equivalent DDL automatically on first initialization.
CREATE TABLE IF NOT EXISTS sensitive_records (
    id UUID PRIMARY KEY,
    record_type VARCHAR(50) NOT NULL,
    ciphertext BYTEA NOT NULL,
    nonce BYTEA NOT NULL,
    encrypted_dek TEXT NOT NULL,
    kek_name VARCHAR(100) NOT NULL,
    kek_version SMALLINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(80) NOT NULL,
    outcome VARCHAR(20) NOT NULL,
    record_id UUID NULL,
    details TEXT NOT NULL DEFAULT '{}',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE sensitive_records TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE audit_events TO app_user;
GRANT USAGE, SELECT ON SEQUENCE audit_events_id_seq TO app_user;
