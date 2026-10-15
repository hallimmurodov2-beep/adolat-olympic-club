-- An acknowledged submission remains replayable after its deadline; changed
-- payload and unauthorized new work still fail. One-owner prototype only.
BEGIN;
CREATE OR REPLACE FUNCTION api.submit_personal_attempt(item uuid, client_id uuid, answer jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE a app.activities%ROWTYPE; previous app.submissions%ROWTYPE; sid uuid;
BEGIN
 IF NOT app_private.caller_enabled() OR NOT EXISTS(
 SELECT 1 FROM app.profiles WHERE user_id=auth.uid() AND role='student' AND active)
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF answer IS NULL OR length(answer::text)>250000 OR client_id IS NULL
 THEN RAISE EXCEPTION 'invalid_answer' USING ERRCODE='22023'; END IF;
 -- Re-check a previously acknowledged request BEFORE deadline enforcement.
 SELECT * INTO previous FROM app.submissions s WHERE s.owner_id=auth.uid()
 AND s.client_id=submit_personal_attempt.client_id;
 IF FOUND THEN
  IF previous.item_id<>item OR previous.body<>answer
  THEN RAISE EXCEPTION 'client_id_payload_conflict' USING ERRCODE='23505'; END IF;
  RETURN jsonb_build_object('id',previous.id,'submitted_at',previous.submitted_at,'replayed',true);
 END IF;
 SELECT a.* INTO a FROM app.activities a JOIN app.activity_items i ON i.activity_id=a.id
 WHERE i.id=item FOR UPDATE OF a;
 IF NOT FOUND OR a.status NOT IN ('published','active') OR clock_timestamp()<a.starts_at
 OR clock_timestamp()>=a.ends_at OR NOT EXISTS(
  SELECT 1 FROM app.classroom_memberships m WHERE m.classroom_id=a.classroom_id
   AND m.student_id=auth.uid())
 THEN RAISE EXCEPTION 'submission_not_allowed' USING ERRCODE='42501'; END IF;
 -- Serialize all fresh attempts for a given activity before checking duplicate.
 SELECT * INTO previous FROM app.submissions s WHERE s.owner_id=auth.uid()
 AND s.client_id=submit_personal_attempt.client_id;
 IF FOUND THEN
  IF previous.item_id<>item OR previous.body<>answer
  THEN RAISE EXCEPTION 'client_id_payload_conflict' USING ERRCODE='23505'; END IF;
  RETURN jsonb_build_object('id',previous.id,'submitted_at',previous.submitted_at,'replayed',true);
 END IF;
 INSERT INTO app.submissions(item_id,owner_id,client_id,body)
 VALUES(item,auth.uid(),client_id,answer) RETURNING id INTO sid;
 INSERT INTO app_private.audit_events(actor_id,action,target_id)
 VALUES(auth.uid(),'submission.created',sid);
 RETURN (SELECT jsonb_build_object('id',s.id,'submitted_at',s.submitted_at,'replayed',false)
 FROM app.submissions s WHERE s.id=sid);
END $$;
REVOKE ALL ON FUNCTION api.submit_personal_attempt(uuid,uuid,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.submit_personal_attempt(uuid,uuid,jsonb) TO authenticated;
COMMIT;
