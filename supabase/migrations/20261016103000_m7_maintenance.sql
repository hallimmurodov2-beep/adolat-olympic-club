-- M7 maintenance: expire abandoned reservations; return cleanup paths only to trusted service.
BEGIN;
CREATE FUNCTION api.edge_expire_uploads(max_count integer DEFAULT 40) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE i record; paths jsonb:='[]'::jsonb;
BEGIN
 IF auth.role()<>'service_role' OR max_count NOT BETWEEN 1 AND 100 THEN
 RAISE EXCEPTION 'service_only' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM app_private.storage_budget WHERE id=1 FOR UPDATE;
 FOR i IN SELECT id,object_path,expected_bytes,state
 FROM app_private.upload_intents
 WHERE state IN('reserved','expired') AND expires_at<now()
 ORDER BY expires_at,id LIMIT max_count FOR UPDATE SKIP LOCKED LOOP
  IF i.state='reserved' THEN
    UPDATE app_private.storage_budget SET reserved_bytes=reserved_bytes-i.expected_bytes WHERE id=1;
    UPDATE app_private.upload_intents SET state='expired' WHERE id=i.id;
  END IF;
  paths:=paths||jsonb_build_array(i.object_path);
 END LOOP;
 RETURN paths;
END $$;
REVOKE ALL ON FUNCTION api.edge_expire_uploads(integer) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.edge_expire_uploads(integer) TO service_role;
COMMIT;
