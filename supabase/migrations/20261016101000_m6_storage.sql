-- M6 private Storage: stage -> validate -> promote. Zero direct accepted-file writes.
BEGIN;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='olympiados')
THEN RAISE EXCEPTION 'Do not run on legacy database'; END IF; END $$;
CREATE TABLE app_private.storage_budget (
 id integer PRIMARY KEY DEFAULT 1 CHECK(id=1),
 reserved_bytes bigint NOT NULL DEFAULT 0 CHECK(reserved_bytes>=0),
 committed_bytes bigint NOT NULL DEFAULT 0 CHECK(committed_bytes>=0),
 CHECK(reserved_bytes+committed_bytes<=734003200)
);
INSERT INTO app_private.storage_budget(id) VALUES(1);
CREATE TABLE app_private.upload_intents (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 owner_id uuid NOT NULL REFERENCES app.profiles(user_id),
 client_id uuid NOT NULL,
 classroom_id uuid NOT NULL REFERENCES app.classrooms(id),
 target_kind text NOT NULL CHECK(target_kind IN ('problem','draft')),
 target_id uuid NOT NULL,
 original_name text NOT NULL CHECK(length(original_name) BETWEEN 1 AND 180),
 media_type text NOT NULL CHECK(media_type IN ('application/pdf','text/plain',
 'image/jpeg','image/png','image/webp')),
 expected_bytes integer NOT NULL CHECK(expected_bytes BETWEEN 1 AND 8388608),
 expected_sha256 text NOT NULL CHECK(expected_sha256 ~ '^[0-9a-f]{64}$'),
 object_path text NOT NULL UNIQUE,
 state text NOT NULL DEFAULT 'reserved'
 CHECK(state IN ('reserved','validating','accepted','failed','expired')),
 accepted_file_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL DEFAULT (now()+interval '20 minutes'),
 UNIQUE(owner_id,client_id)
);
CREATE INDEX upload_intents_expiry_idx ON app_private.upload_intents(state,expires_at);
CREATE INDEX upload_intents_owner_idx ON app_private.upload_intents(owner_id);
CREATE TABLE app.stored_files (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 owner_id uuid NOT NULL REFERENCES app.profiles(user_id),
 classroom_id uuid NOT NULL REFERENCES app.classrooms(id),
 target_kind text NOT NULL CHECK(target_kind IN ('problem','draft')),
 target_id uuid NOT NULL,
 filename text NOT NULL CHECK(length(filename) BETWEEN 1 AND 180),
 mime text NOT NULL CHECK(mime IN ('application/pdf','text/plain','image/png','image/jpeg')),
 size_bytes integer NOT NULL CHECK(size_bytes BETWEEN 1 AND 8388608),
 sha256 text NOT NULL CHECK(sha256 ~ '^[0-9a-f]{64}$'),
 object_path text NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX stored_files_target_idx ON app.stored_files(target_kind,target_id);
CREATE INDEX stored_files_owner_idx ON app.stored_files(owner_id);
ALTER TABLE app_private.upload_intents ADD CONSTRAINT upload_intents_accepted_fk
 FOREIGN KEY(accepted_file_id) REFERENCES app.stored_files(id);
CREATE TABLE app.submission_files(
 submission_id uuid NOT NULL REFERENCES app.submissions(id),
 file_id uuid NOT NULL REFERENCES app.stored_files(id),
 PRIMARY KEY(submission_id,file_id)
);
-- Each new table denies all browser access; privileged, reviewed RPCs only.
DO $$ DECLARE t record; BEGIN
 FOR t IN SELECT schemaname,tablename FROM pg_tables
 WHERE (schemaname='app' AND tablename IN('stored_files','submission_files'))
 OR (schemaname='app_private' AND tablename IN('storage_budget','upload_intents'))
 LOOP
 EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',t.schemaname,t.tablename);
 EXECUTE format('REVOKE ALL ON %I.%I FROM PUBLIC,anon,authenticated',t.schemaname,t.tablename);
 END LOOP;
END $$;
INSERT INTO storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
VALUES ('adolat-quarantine','adolat-quarantine',false,8388608,
 ARRAY['application/pdf','text/plain','image/jpeg','image/png','image/webp']),
 ('adolat-files','adolat-files',false,8388608,
 ARRAY['application/pdf','text/plain','image/png','image/jpeg'])
ON CONFLICT(id) DO NOTHING;
CREATE FUNCTION app_private.can_use_upload_target(kind text,target uuid) RETURNS uuid
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
DECLARE cid uuid;
BEGIN
 IF NOT app_private.caller_enabled() THEN RETURN NULL; END IF;
 IF kind='problem' THEN
  SELECT p.classroom_id INTO cid FROM app.problems p WHERE p.id=target;
  IF cid IS NOT NULL AND app_private.manages_classroom(cid) THEN RETURN cid; END IF;
 ELSIF kind='draft' THEN
  SELECT a.classroom_id INTO cid FROM app.activity_items i
   JOIN app.activities a ON a.id=i.activity_id WHERE i.id=target
   AND a.status IN ('published','active') AND clock_timestamp()<a.ends_at;
  IF cid IS NOT NULL AND EXISTS(SELECT 1 FROM app.classroom_memberships cm
   WHERE cm.classroom_id=cid AND cm.student_id=auth.uid()) THEN RETURN cid; END IF;
 END IF;
 RETURN NULL;
END $$;
CREATE FUNCTION api.reserve_upload(kind text,target uuid,client_id uuid,filename text,
 mime text,bytes integer,sha256 text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE cid uuid; intent app_private.upload_intents%ROWTYPE;
 actor_role text; allowed_limit bigint;
BEGIN
 cid:=app_private.can_use_upload_target(kind,target);
 IF cid IS NULL OR client_id IS NULL OR filename IS NULL OR length(trim(filename)) NOT BETWEEN 1 AND 180
 OR filename ~ '[\\/[:cntrl:]]' OR mime NOT IN('application/pdf','text/plain','image/jpeg','image/png','image/webp')
 OR bytes NOT BETWEEN 1 AND 8388608 OR sha256 !~ '^[0-9a-f]{64}$'
 THEN RAISE EXCEPTION 'upload_not_allowed' USING ERRCODE='42501'; END IF;
 SELECT role INTO actor_role FROM app.profiles WHERE user_id=auth.uid();
 allowed_limit:=CASE WHEN actor_role='student' THEN 33554432 ELSE 134217728 END;
 PERFORM 1 FROM app_private.storage_budget WHERE id=1 FOR UPDATE;
 SELECT * INTO intent FROM app_private.upload_intents i WHERE i.owner_id=auth.uid()
 AND i.client_id=reserve_upload.client_id;
 IF FOUND THEN
  IF intent.expected_sha256<>sha256 OR intent.expected_bytes<>bytes
   OR intent.target_kind<>kind OR intent.target_id<>target OR intent.state<>'reserved'
   OR intent.expires_at<=now() THEN
   RAISE EXCEPTION 'upload_conflict' USING ERRCODE='23505'; END IF;
 ELSE
  IF (SELECT count(*) FROM app.stored_files f WHERE f.target_kind=kind AND f.target_id=target)
   +(SELECT count(*) FROM app_private.upload_intents i WHERE i.target_kind=kind
      AND i.target_id=target AND i.state='reserved' AND i.expires_at>now())>=12
   OR (SELECT coalesce(sum(size_bytes),0) FROM app.stored_files WHERE owner_id=auth.uid())
   +(SELECT coalesce(sum(expected_bytes),0) FROM app_private.upload_intents
     WHERE owner_id=auth.uid() AND state='reserved' AND expires_at>now())+bytes>allowed_limit
   OR (SELECT committed_bytes+reserved_bytes+bytes FROM app_private.storage_budget WHERE id=1)>734003200
  THEN RAISE EXCEPTION 'upload_quota' USING ERRCODE='23514'; END IF;
  INSERT INTO app_private.upload_intents(owner_id,client_id,classroom_id,target_kind,
   target_id,original_name,media_type,expected_bytes,expected_sha256,object_path)
  VALUES(auth.uid(),client_id,cid,kind,target,filename,mime,bytes,sha256,
    'quarantine/'||auth.uid()::text||'/'||gen_random_uuid()::text)
  RETURNING * INTO intent;
  UPDATE app_private.storage_budget SET reserved_bytes=reserved_bytes+bytes WHERE id=1;
 END IF;
 RETURN jsonb_build_object('id',intent.id,'object_path',intent.object_path,
 'expires_at',intent.expires_at,'bucket','adolat-quarantine');
END $$;
CREATE FUNCTION app_private.authorize_quarantine_path(name text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT app_private.caller_enabled() AND EXISTS(
  SELECT 1 FROM app_private.upload_intents i WHERE i.object_path=name
  AND i.owner_id=auth.uid() AND i.state='reserved' AND i.expires_at>now()
  AND app_private.can_use_upload_target(i.target_kind,i.target_id)=i.classroom_id);
$$;
-- Quarantine INSERT only; no SELECT, listing, UPDATE, DELETE or signed URLs.
DROP POLICY IF EXISTS adolat_quarantine_insert ON storage.objects;
CREATE POLICY adolat_quarantine_insert ON storage.objects FOR INSERT TO authenticated
WITH CHECK(bucket_id='adolat-quarantine' AND
 app_private.authorize_quarantine_path(name));
-- Accepted files may never be accessed directly; use authenticated Edge gateway.
CREATE FUNCTION api.file_metadata(file uuid) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
DECLARE f app.stored_files%ROWTYPE;
BEGIN
 IF NOT app_private.caller_enabled() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 SELECT * INTO f FROM app.stored_files WHERE id=file;
 IF NOT FOUND THEN RAISE EXCEPTION 'not_found' USING ERRCODE='42501'; END IF;
 IF f.target_kind='draft' THEN
  IF f.owner_id<>auth.uid() AND NOT EXISTS (
   SELECT 1 FROM app.submission_files sf JOIN app.submissions s ON s.id=sf.submission_id
   JOIN app.activity_items i ON i.id=s.item_id JOIN app.activities a ON a.id=i.activity_id
   WHERE sf.file_id=file AND app_private.manages_classroom(a.classroom_id))
  THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 ELSE
  IF NOT app_private.has_classroom_access(f.classroom_id)
   OR NOT EXISTS(SELECT 1 FROM app.problems p
    WHERE p.id=f.target_id AND p.classroom_id=f.classroom_id
    AND (p.published OR app_private.manages_classroom(p.classroom_id)))
  THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 END IF;
 RETURN jsonb_build_object('id',f.id,'filename',f.filename,'mime',f.mime,
 'size_bytes',f.size_bytes,'created_at',f.created_at);
END $$;
-- Service role lookup used only after caller is checked with api.file_metadata.
CREATE FUNCTION api.edge_upload_intent(intent uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE i app_private.upload_intents%ROWTYPE;
BEGIN
 IF auth.role()<>'service_role' THEN RAISE EXCEPTION 'service_only' USING ERRCODE='42501'; END IF;
 SELECT * INTO i FROM app_private.upload_intents WHERE id=intent;
 IF NOT FOUND OR i.expires_at<=now() OR i.state NOT IN('reserved','accepted') THEN RETURN NULL; END IF;
 RETURN jsonb_build_object('id',i.id,'owner_id',i.owner_id,'classroom_id',i.classroom_id,
 'target_kind',i.target_kind,'target_id',i.target_id,'object_path',i.object_path,
 'original_name',i.original_name,'media_type',i.media_type,'expected_bytes',i.expected_bytes,
 'expected_sha256',i.expected_sha256,'state',i.state,'accepted_file_id',i.accepted_file_id);
END $$;
CREATE FUNCTION api.edge_finish_upload(intent uuid,accepted_name text,new_mime text,
 clean_sha256 text,clean_bytes integer) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE i app_private.upload_intents%ROWTYPE; fid uuid;
BEGIN
 IF auth.role()<>'service_role' THEN RAISE EXCEPTION 'service_only' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM app_private.storage_budget WHERE id=1 FOR UPDATE;
 SELECT * INTO i FROM app_private.upload_intents WHERE id=intent FOR UPDATE;
 IF NOT FOUND OR i.expires_at<=now() OR i.state<>'reserved'
 OR accepted_name IS NULL OR new_mime NOT IN ('text/plain','application/pdf','image/png','image/jpeg')
 OR clean_sha256 !~ '^[0-9a-f]{64}$' OR clean_bytes NOT BETWEEN 1 AND 8388608
 OR accepted_name <> 'accepted/'||i.id::text OR
 clean_bytes>i.expected_bytes
 THEN RAISE EXCEPTION 'upload_finalization_denied' USING ERRCODE='42501'; END IF;
 -- Re-check owner and currently valid target after time spent on Storage.
 IF NOT EXISTS(SELECT 1 FROM app.profiles p WHERE p.user_id=i.owner_id AND p.active)
 OR NOT EXISTS(SELECT 1 FROM app.classrooms c WHERE c.id=i.classroom_id AND c.active)
 THEN RAISE EXCEPTION 'upload_owner_inactive' USING ERRCODE='42501'; END IF;
 INSERT INTO app.stored_files(owner_id,classroom_id,target_kind,target_id,
  filename,mime,size_bytes,sha256,object_path)
 VALUES(i.owner_id,i.classroom_id,i.target_kind,i.target_id,
 i.original_name,new_mime,clean_bytes,clean_sha256,accepted_name) RETURNING id INTO fid;
 UPDATE app_private.upload_intents SET state='accepted',accepted_file_id=fid
 WHERE id=intent;
 UPDATE app_private.storage_budget SET reserved_bytes=reserved_bytes-i.expected_bytes,
 committed_bytes=committed_bytes+clean_bytes WHERE id=1;
 RETURN fid;
END $$;
CREATE FUNCTION api.edge_file_location(fid uuid) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF auth.role()<>'service_role' THEN RAISE EXCEPTION 'service_only' USING ERRCODE='42501'; END IF;
 RETURN (SELECT object_path FROM app.stored_files WHERE id=fid);
END $$;
REVOKE ALL ON FUNCTION app_private.can_use_upload_target(text,uuid),
 app_private.authorize_quarantine_path(text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION app_private.can_use_upload_target(text,uuid),
 app_private.authorize_quarantine_path(text) TO authenticated;
REVOKE ALL ON FUNCTION api.reserve_upload(text,uuid,uuid,text,text,integer,text),
 api.file_metadata(uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.reserve_upload(text,uuid,uuid,text,text,integer,text),
 api.file_metadata(uuid) TO authenticated;
REVOKE ALL ON FUNCTION api.edge_upload_intent(uuid),api.edge_finish_upload(uuid,text,text,text,integer),
 api.edge_file_location(uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.edge_upload_intent(uuid),api.edge_finish_upload(uuid,text,text,text,integer),
 api.edge_file_location(uuid) TO service_role;
COMMIT;
