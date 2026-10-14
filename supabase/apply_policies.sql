-- Run as the SAME operator that owns the Alembic-created application tables.
-- Repeat after every schema migration, before opening the web runtime.
-- Do not expose the olympiados schema via Supabase's Data API settings.
BEGIN;
DO $$
DECLARE tab record; browser_role text;
BEGIN
  IF current_user='olympiados_app' THEN RAISE EXCEPTION 'Operator identity required'; END IF;
  IF NOT EXISTS (SELECT FROM pg_namespace WHERE nspname='olympiados') THEN
    RAISE EXCEPTION 'Run bootstrap.sql first';
  END IF;
  IF (SELECT nspowner=(SELECT oid FROM pg_roles WHERE rolname='olympiados_app') FROM pg_namespace WHERE nspname='olympiados') THEN
    RAISE EXCEPTION 'Runtime must not own the schema';
  END IF;
  FOR tab IN SELECT tablename FROM pg_tables WHERE schemaname='olympiados' LOOP
    EXECUTE format('REVOKE ALL ON TABLE olympiados.%I FROM PUBLIC, olympiados_app', tab.tablename);
    FOREACH browser_role IN ARRAY ARRAY['anon','authenticated'] LOOP
      IF EXISTS (SELECT FROM pg_roles WHERE rolname=browser_role) THEN
        EXECUTE format('REVOKE ALL ON TABLE olympiados.%I FROM %I', tab.tablename, browser_role);
      END IF;
    END LOOP;
    EXECUTE format('ALTER TABLE olympiados.%I ENABLE ROW LEVEL SECURITY', tab.tablename);
    EXECUTE format('ALTER TABLE olympiados.%I FORCE ROW LEVEL SECURITY', tab.tablename);
    EXECUTE format('DROP POLICY IF EXISTS adolat_backend ON olympiados.%I', tab.tablename);
    EXECUTE format('DROP POLICY IF EXISTS adolat_operator ON olympiados.%I', tab.tablename);
    EXECUTE format('CREATE POLICY adolat_operator ON olympiados.%I TO %I USING (true) WITH CHECK (true)', tab.tablename, current_user);
    IF tab.tablename='alembic_version' THEN
      EXECUTE format('GRANT SELECT ON TABLE olympiados.%I TO olympiados_app', tab.tablename);
      EXECUTE format('CREATE POLICY adolat_backend ON olympiados.%I FOR SELECT TO olympiados_app USING (true)', tab.tablename);
    ELSE
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE olympiados.%I TO olympiados_app', tab.tablename);
      EXECUTE format('CREATE POLICY adolat_backend ON olympiados.%I TO olympiados_app USING (true) WITH CHECK (true)', tab.tablename);
    END IF;
  END LOOP;
  REVOKE ALL ON ALL SEQUENCES IN SCHEMA olympiados FROM PUBLIC, olympiados_app;
  GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA olympiados TO olympiados_app;
  FOREACH browser_role IN ARRAY ARRAY['anon','authenticated'] LOOP
    IF EXISTS (SELECT FROM pg_roles WHERE rolname=browser_role) THEN
      EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA olympiados FROM %I', browser_role);
    END IF;
  END LOOP;
END $$;
COMMIT;
-- USING(true) is an explicit backend-role allowance, not student row isolation.
-- FastAPI authorization remains the per-student/circle/classroom boundary.
