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

-- Privilege bundle inherited by short-lived Vault database roles.
-- NOLOGIN: nothing authenticates as app_writer itself.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_writer') THEN
        CREATE ROLE app_writer NOLOGIN;
    ELSE
        ALTER ROLE app_writer WITH NOLOGIN;
    END IF;
END
$$;

-- Least privilege for the Vault database plugin (D-05).
-- CREATEROLE: create and drop the dynamic login roles it owns.
-- NOINHERIT: membership in app_writer does not give this role table access.
-- NOSUPERUSER / NOCREATEDB: cannot bypass grants or create databases.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vault_admin') THEN
        CREATE ROLE vault_admin
            WITH LOGIN NOSUPERUSER NOCREATEDB CREATEROLE NOINHERIT
            PASSWORD 'local_vault_admin_password';
    ELSE
        ALTER ROLE vault_admin
            WITH LOGIN NOSUPERUSER NOCREATEDB CREATEROLE NOINHERIT
            PASSWORD 'local_vault_admin_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE encryption_db TO app_user;
GRANT CONNECT ON DATABASE encryption_db TO vault_admin;
GRANT CONNECT ON DATABASE encryption_db TO app_writer;
-- ADMIN OPTION lets vault_admin grant app_writer to dynamic roles without inheriting it.
GRANT app_writer TO vault_admin WITH ADMIN OPTION;
