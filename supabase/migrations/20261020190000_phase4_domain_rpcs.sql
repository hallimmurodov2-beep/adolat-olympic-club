-- Phase 4 incremental transactional API. New isolated project ONLY.
BEGIN;
CREATE OR REPLACE FUNCTION api.revoke_my_session() RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE sid text := auth.jwt()->>'session_id';
BEGIN
 IF auth.uid() IS NULL OR sid IS NULL OR length(sid)<10 THEN RETURN false; END IF;
 INSERT INTO app_private.revoked_sessions(session_id,user_id,reason)
 VALUES(sid,auth.uid(),'logout') ON CONFLICT(session_id) DO NOTHING;
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION api.revoke_my_session() FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION api.revoke_my_session() TO authenticated;

CREATE OR REPLACE FUNCTION api.submit_answer(p_item uuid,p_client uuid,p_body jsonb)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE result uuid; classroom uuid; activity_status text;
BEGIN
 IF NOT app_private.caller_enabled() THEN RAISE EXCEPTION 'account_disabled' USING ERRCODE='42501'; END IF;
 IF p_body IS NULL OR jsonb_typeof(p_body)<>'object' OR octet_length(p_body::text)>32768 THEN RAISE EXCEPTION 'invalid_body'; END IF;
 SELECT a.classroom_id,a.status INTO classroom,activity_status
 FROM app.activity_items i JOIN app.activities a ON a.id=i.activity_id WHERE i.id=p_item;
 IF classroom IS NULL OR activity_status NOT IN ('published','active') OR NOT EXISTS(
 SELECT 1 FROM app.classroom_memberships m WHERE m.classroom_id=classroom AND m.student_id=auth.uid())
 THEN RAISE EXCEPTION 'submission_not_allowed' USING ERRCODE='42501'; END IF;
 INSERT INTO app.submissions(item_id,owner_id,client_id,body)
 VALUES(p_item,auth.uid(),p_client,p_body)
 ON CONFLICT(owner_id,client_id) DO UPDATE SET body=app.submissions.body
 RETURNING id INTO result;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION api.submit_answer(uuid,uuid,jsonb) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION api.submit_answer(uuid,uuid,jsonb) TO authenticated;

CREATE OR REPLACE FUNCTION api.grade_submission(p_submission uuid,p_score numeric,p_feedback jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE target_classroom uuid;
BEGIN
 SELECT a.classroom_id INTO target_classroom FROM app.submissions s
 JOIN app.activity_items i ON i.id=s.item_id JOIN app.activities a ON a.id=i.activity_id
 WHERE s.id=p_submission;
 IF target_classroom IS NULL OR NOT app_private.manages_classroom(target_classroom)
 THEN RAISE EXCEPTION 'grading_forbidden' USING ERRCODE='42501'; END IF;
 IF p_score IS NULL OR p_score<0 OR p_score>100 OR p_feedback IS NULL OR jsonb_typeof(p_feedback)<>'object'
 OR octet_length(p_feedback::text)>16384 THEN RAISE EXCEPTION 'invalid_grade'; END IF;
 INSERT INTO app_private.grades(submission_id,score,feedback)
 VALUES(p_submission,p_score,p_feedback)
 ON CONFLICT(submission_id) DO UPDATE SET score=excluded.score,feedback=excluded.feedback,
 version=app_private.grades.version+1,released_at=NULL;
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION api.grade_submission(uuid,numeric,jsonb) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION api.grade_submission(uuid,numeric,jsonb) TO authenticated;

CREATE OR REPLACE FUNCTION api.save_training_plan(p_cycle uuid,p_goal text,p_review text,p_next_step text,p_context jsonb)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE target uuid; result uuid;
BEGIN
 IF NOT app_private.caller_enabled() THEN RAISE EXCEPTION 'account_disabled' USING ERRCODE='42501'; END IF;
 SELECT owner_id INTO target FROM app.training_cycles WHERE id=p_cycle;
 IF target IS DISTINCT FROM auth.uid() THEN RAISE EXCEPTION 'cycle_forbidden' USING ERRCODE='42501'; END IF;
 IF p_goal IS NULL OR p_review IS NULL OR p_next_step IS NULL OR p_context IS NULL
 OR length(p_goal)>8000 OR length(p_review)>16000 OR length(p_next_step)>8000
 OR jsonb_typeof(p_context)<>'object' OR octet_length(p_context::text)>32768
 THEN RAISE EXCEPTION 'invalid_plan'; END IF;
 INSERT INTO app.training_plans(cycle_id,owner_id,goal,review,next_step,context)
 VALUES(p_cycle,auth.uid(),p_goal,p_review,p_next_step,p_context)
 ON CONFLICT(cycle_id,owner_id) DO UPDATE SET goal=excluded.goal,review=excluded.review,
 next_step=excluded.next_step,context=excluded.context,version=app.training_plans.version+1,updated_at=now()
 RETURNING id INTO result;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION api.save_training_plan(uuid,text,text,text,jsonb) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION api.save_training_plan(uuid,text,text,text,jsonb) TO authenticated;

CREATE OR REPLACE FUNCTION api.join_training_circle(p_circle uuid)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE target app.training_circles%ROWTYPE;
BEGIN
 IF NOT app_private.caller_enabled() THEN RAISE EXCEPTION 'account_disabled' USING ERRCODE='42501'; END IF;
 SELECT * INTO target FROM app.training_circles WHERE id=p_circle FOR UPDATE;
 IF NOT FOUND OR target.archived OR target.locked OR NOT target.discoverable OR target.subject_id<>'informatics'
 THEN RAISE EXCEPTION 'circle_unavailable' USING ERRCODE='42501'; END IF;
 INSERT INTO app.circle_members(circle_id,user_id,status)
 VALUES(p_circle,auth.uid(),'pending')
 ON CONFLICT(circle_id,user_id) DO NOTHING;
 RETURN (SELECT status FROM app.circle_members WHERE circle_id=p_circle AND user_id=auth.uid());
END $$;
REVOKE ALL ON FUNCTION api.join_training_circle(uuid) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION api.join_training_circle(uuid) TO authenticated;
COMMIT;
