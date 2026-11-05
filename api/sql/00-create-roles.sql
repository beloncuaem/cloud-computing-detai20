-- Run this file while connected to database encryption_db or postgres
-- as a PostgreSQL administrator (typically user postgres).
-- Demo-only passwords: change them in this file and in .env before use.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN PASSWORD 'local_app_password';
    ELSE
        ALTER ROLE app_user WITH LOGIN PASSWORD 'local_app_password';
    END IF;
END
$$;

-- SUPERUSER is used only to simplify local Vault Database Secrets Engine setup.
-- Do NOT use this permission design in a real or shared environment.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vault_admin') THEN
        CREATE ROLE vault_admin WITH LOGIN SUPERUSER PASSWORD 'local_vault_admin_password';
    ELSE
        ALTER ROLE vault_admin WITH LOGIN SUPERUSER PASSWORD 'local_vault_admin_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE encryption_db TO app_user;
GRANT CONNECT ON DATABASE encryption_db TO vault_admin;
