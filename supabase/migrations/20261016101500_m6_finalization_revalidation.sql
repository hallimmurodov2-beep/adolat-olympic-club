-- Strengthen finalization against revoked memberships during Storage I/O.
BEGIN;
CREATE OR REPLACE FUNCTION api.edge_finish_upload(intent uuid,accepted_name text,new_mime text,
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
 -- Recheck the exact *original owner* against fresh role, classroom and
 -- assignment state. The Edge caller is a service role, not the owner.
 IF i.target_kind='problem' THEN
   IF NOT EXISTS(
     SELECT 1 FROM app.problems p
     JOIN app.classrooms c ON c.id=p.classroom_id
     JOIN app.profiles u ON u.user_id=i.owner_id
     WHERE p.id=i.target_id AND c.id=i.classroom_id AND c.active
       AND u.active AND (u.role='admin' OR (u.role='teacher' AND c.teacher_id=i.owner_id))
   ) THEN RAISE EXCEPTION 'upload_access_revoked' USING ERRCODE='42501'; END IF;
 ELSIF i.target_kind='draft' THEN
   IF NOT EXISTS(
     SELECT 1 FROM app.activity_items ai
     JOIN app.activities a ON a.id=ai.activity_id
     JOIN app.classroom_memberships cm ON cm.classroom_id=a.classroom_id
     JOIN app.profiles u ON u.user_id=cm.student_id
     WHERE ai.id=i.target_id AND a.classroom_id=i.classroom_id AND cm.student_id=i.owner_id
       AND u.role='student' AND u.active AND a.status IN('published','active')
       AND clock_timestamp()<a.ends_at
   ) THEN RAISE EXCEPTION 'upload_access_revoked' USING ERRCODE='42501'; END IF;
 ELSE RAISE EXCEPTION 'unsupported_upload_target' USING ERRCODE='42501'; END IF;
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

COMMIT;
