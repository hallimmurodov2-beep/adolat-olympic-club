-- Adolat Olympic Club: operator-only, NEW project bootstrap; no embedded password.
-- Run before Alembic as the migration/operator owner (never olympiados_app).
-- This establishes a private, backend-mediated schema, NOT per-student SQL RLS.
BEGIN;
DO $$
BEGIN
  IF current_user = 'olympiados_app' THEN
    RAISE EXCEPTION 'Use the separate operator identity';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='olympiados_app') THEN
    CREATE ROLE olympiados_app NOLOGIN NOCREATEDB NOCREATEROLE NOINHERIT;
    -- New roles default to no superuser/replication/BYPASSRLS attributes.
  END IF;
  IF EXISTS (SELECT FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='olympiados_app')) THEN
    RAISE EXCEPTION 'Runtime role has inherited/assumable memberships; review and remove them';
  END IF;
  IF EXISTS (SELECT FROM pg_roles WHERE rolname='olympiados_app' AND
      (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit)) THEN
    RAISE EXCEPTION 'Existing runtime attributes are unsafe; resolve with an authorized operator, do not silently reuse';
  END IF;
END $$;
-- Do not ALTER SUPERUSER/REPLICATION attributes unconditionally: a managed
-- database operator is not necessarily a cluster superuser. Fail closed above.
CREATE SCHEMA IF NOT EXISTS olympiados;
REVOKE ALL ON SCHEMA olympiados FROM PUBLIC, olympiados_app;
GRANT USAGE ON SCHEMA olympiados TO olympiados_app;
-- PostgreSQL 15+ defaults already restrict public creation on fresh clusters.
-- Explicitly prevent old PUBLIC CREATE defaults from providing a DDL side door.
REVOKE CREATE ON SCHEMA public FROM PUBLIC, olympiados_app;
DO $$
DECLARE browser_role text;
BEGIN
  FOREACH browser_role IN ARRAY ARRAY['anon','authenticated'] LOOP
    IF EXISTS (SELECT FROM pg_roles WHERE rolname=browser_role) THEN
      EXECUTE format('REVOKE ALL ON SCHEMA olympiados FROM %I', browser_role);
    END IF;
  END LOOP;
END $$;
ALTER DEFAULT PRIVILEGES IN SCHEMA olympiados REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA olympiados REVOKE ALL ON SEQUENCES FROM PUBLIC;
-- No runtime DML default grants: apply_policies.sql explicitly handles every
-- migrated table. New tables fail closed until that operator step succeeds.
COMMIT;
-- Set a long random password using psql's \password olympiados_app on a private
-- operator connection, then ALTER ROLE olympiados_app LOGIN. Never commit it.
