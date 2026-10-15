-- M6 Edge-to-DB boundaries. app_private MUST NOT be exposed in Supabase Data API.
BEGIN;
CREATE FUNCTION api.edge_reserve_codeforces_fetch() RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF auth.role()<>'service_role' THEN RAISE EXCEPTION 'service_only' USING ERRCODE='42501'; END IF;
 RETURN app_private.reserve_codeforces_fetch();
END $$;
CREATE FUNCTION api.edge_store_codeforces_profile(account uuid, expected_version integer, profile jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF auth.role()<>'service_role' THEN RAISE EXCEPTION 'service_only' USING ERRCODE='42501'; END IF;
 RETURN app_private.store_codeforces_profile(account,expected_version,profile);
END $$;
CREATE FUNCTION api.edge_store_codeforces_contests(contests jsonb) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF auth.role()<>'service_role' THEN RAISE EXCEPTION 'service_only' USING ERRCODE='42501'; END IF;
 RETURN app_private.store_codeforces_contests(contests);
END $$;
REVOKE ALL ON FUNCTION api.edge_reserve_codeforces_fetch(),
 api.edge_store_codeforces_profile(uuid,integer,jsonb),
 api.edge_store_codeforces_contests(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.edge_reserve_codeforces_fetch(),
 api.edge_store_codeforces_profile(uuid,integer,jsonb),
 api.edge_store_codeforces_contests(jsonb) TO service_role;
INSERT INTO app_private.codeforces_contest_cache(id) VALUES(1) ON CONFLICT DO NOTHING;
COMMIT;
