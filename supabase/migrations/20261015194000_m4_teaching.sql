-- M4 incremental: server-authoritative teaching foundation.
-- No generic table INSERT/UPDATE/DELETE permissions are granted to browsers.
BEGIN;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='olympiados')
 THEN RAISE EXCEPTION 'Not a new isolated staging project'; END IF; END $$;

CREATE FUNCTION app_private.is_current_staff() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT app_private.caller_enabled() AND EXISTS (
  SELECT 1 FROM app.profiles p WHERE p.user_id=auth.uid()
   AND p.role IN ('teacher','admin'));
$$;
REVOKE ALL ON FUNCTION app_private.is_current_staff() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION app_private.is_current_staff() TO authenticated;

CREATE FUNCTION api.create_classroom(subject text, classroom_name jsonb) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE id_result uuid;
BEGIN
 IF NOT app_private.is_current_staff() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF subject NOT IN ('math','physics','informatics') OR jsonb_typeof(classroom_name)<>'object'
 OR length(classroom_name::text)>2000
 THEN RAISE EXCEPTION 'invalid_input' USING ERRCODE='22023'; END IF;
 INSERT INTO app.classrooms(subject_id,teacher_id,name)
 VALUES(subject,auth.uid(),classroom_name) RETURNING id INTO id_result;
 INSERT INTO app_private.audit_events(actor_id,action,target_id) VALUES(auth.uid(),'classroom.created',id_result);
 RETURN id_result;
END $$;

CREATE FUNCTION api.change_classroom_membership(room uuid, student uuid, enroll boolean)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE r app.classrooms%ROWTYPE;
BEGIN
 IF NOT app_private.manages_classroom(room) THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 SELECT * INTO r FROM app.classrooms WHERE id=room FOR UPDATE;
 IF NOT FOUND OR NOT r.active OR NOT EXISTS(
  SELECT 1 FROM app.profiles WHERE user_id=student AND role='student' AND active)
 THEN RAISE EXCEPTION 'invalid_input' USING ERRCODE='22023'; END IF;
 IF enroll THEN
  INSERT INTO app.classroom_memberships(classroom_id,student_id)
  VALUES(room,student) ON CONFLICT DO NOTHING;
 ELSE
  DELETE FROM app.classroom_memberships WHERE classroom_id=room AND student_id=student;
 END IF;
 INSERT INTO app_private.audit_events(actor_id,action,target_id)
 VALUES(auth.uid(),CASE WHEN enroll THEN 'classroom.enrolled' ELSE 'classroom.removed' END,room);
 RETURN true;
END $$;

CREATE FUNCTION api.create_problem(room uuid, problem_title jsonb, problem_statement jsonb,
 solution jsonb DEFAULT '{}'::jsonb, hints jsonb DEFAULT '[]'::jsonb)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE pid uuid;
BEGIN
 IF NOT app_private.manages_classroom(room) THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF jsonb_typeof(problem_title)<>'object' OR jsonb_typeof(problem_statement)<>'object'
 OR jsonb_typeof(solution)<>'object' OR jsonb_typeof(hints)<>'array'
 OR length(problem_statement::text)>100000 OR length(solution::text)>100000
 THEN RAISE EXCEPTION 'invalid_input' USING ERRCODE='22023'; END IF;
 INSERT INTO app.problems(classroom_id,title,statement)
 VALUES(room,problem_title,problem_statement) RETURNING id INTO pid;
 INSERT INTO app_private.problem_secrets(problem_id,solution,hints)
 VALUES(pid,solution,hints);
 INSERT INTO app_private.audit_events(actor_id,action,target_id)
 VALUES(auth.uid(),'problem.created',pid);
 RETURN pid;
END $$;

CREATE FUNCTION api.publish_problem(pid uuid, expected_version integer) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE p app.problems%ROWTYPE;
BEGIN
 SELECT * INTO p FROM app.problems WHERE id=pid FOR UPDATE;
 IF NOT FOUND OR NOT app_private.manages_classroom(p.classroom_id)
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF p.version<>expected_version THEN RAISE EXCEPTION 'revision_conflict' USING ERRCODE='40001'; END IF;
 UPDATE app.problems SET published=true,version=version+1 WHERE id=pid
 RETURNING version INTO expected_version;
 RETURN expected_version;
END $$;

CREATE FUNCTION api.list_classroom_problems(room uuid)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
DECLARE staff_ok boolean;
BEGIN
 IF NOT app_private.has_classroom_access(room) THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 staff_ok:=app_private.manages_classroom(room);
 RETURN (SELECT COALESCE(jsonb_agg(jsonb_build_object(
 'id',p.id,'classroom_id',p.classroom_id,'title',p.title,'statement',p.statement,
 'version',p.version,'published',p.published) ORDER BY p.id),'[]'::jsonb)
 FROM app.problems p WHERE p.classroom_id=room AND (p.published OR staff_ok));
END $$;

CREATE FUNCTION api.create_activity(room uuid, activity_kind text, activity_title jsonb,
 starts timestamptz, ends timestamptz) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE aid uuid;
BEGIN
 IF NOT app_private.manages_classroom(room) THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF activity_kind NOT IN ('assignment','session','competition')
 OR jsonb_typeof(activity_title)<>'object' OR ends IS NULL OR starts IS NULL OR ends<=starts
 THEN RAISE EXCEPTION 'invalid_input' USING ERRCODE='22023'; END IF;
 INSERT INTO app.activities(classroom_id,kind,title,starts_at,ends_at)
 VALUES(room,activity_kind,activity_title,starts,ends) RETURNING id INTO aid;
 RETURN aid;
END $$;

CREATE FUNCTION api.add_activity_problem(activity uuid, problem uuid, item_order integer)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE a app.activities%ROWTYPE; p app.problems%ROWTYPE; iid uuid;
BEGIN
 SELECT * INTO a FROM app.activities WHERE id=activity FOR UPDATE;
 IF NOT FOUND OR NOT app_private.manages_classroom(a.classroom_id)
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF a.status<>'draft' THEN RAISE EXCEPTION 'activity_frozen' USING ERRCODE='23514'; END IF;
 SELECT * INTO p FROM app.problems WHERE id=problem AND classroom_id=a.classroom_id;
 IF NOT FOUND OR item_order<0 THEN RAISE EXCEPTION 'invalid_problem' USING ERRCODE='22023'; END IF;
 INSERT INTO app.activity_items(activity_id,problem_id,statement_snapshot,ordinal)
 VALUES(activity,p.id,p.statement,item_order) RETURNING id INTO iid;
 INSERT INTO app_private.item_snapshot_secrets(item_id,solution_snapshot,rubric_snapshot)
 SELECT iid,s.solution,s.rubric FROM app_private.problem_secrets s WHERE s.problem_id=problem;
 RETURN iid;
END $$;

CREATE FUNCTION api.publish_activity(activity uuid, expected_version integer)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE a app.activities%ROWTYPE; newversion integer;
BEGIN
 SELECT * INTO a FROM app.activities WHERE id=activity FOR UPDATE;
 IF NOT FOUND OR NOT app_private.manages_classroom(a.classroom_id)
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF a.status<>'draft' OR a.version<>expected_version
 OR NOT EXISTS(SELECT 1 FROM app.activity_items WHERE activity_id=activity)
 THEN RAISE EXCEPTION 'activity_not_publishable' USING ERRCODE='23514'; END IF;
 UPDATE app.activities SET status='published',version=version+1 WHERE id=activity
 RETURNING version INTO newversion;
 INSERT INTO app_private.audit_events(actor_id,action,target_id) VALUES(auth.uid(),'activity.published',activity);
 RETURN newversion;
END $$;

-- This is a *single-owner, single-answer* initial transaction. Group authorship,
-- full attempt limits and rubric grading are NOT yet implemented; do not use
-- for real timed school competitions until M4 final parity tests pass.
CREATE FUNCTION api.submit_personal_attempt(item uuid, client_id uuid, answer jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE a app.activities%ROWTYPE; prev app.submissions%ROWTYPE; sid uuid;
BEGIN
 IF NOT app_private.caller_enabled() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 SELECT a.* INTO a FROM app.activities a JOIN app.activity_items i ON i.activity_id=a.id
 WHERE i.id=item FOR UPDATE OF a;
 IF NOT FOUND OR a.status NOT IN ('published','active')
 OR clock_timestamp()<a.starts_at OR clock_timestamp()>=a.ends_at
 OR NOT EXISTS(SELECT 1 FROM app.classroom_memberships cm
   WHERE cm.classroom_id=a.classroom_id AND cm.student_id=auth.uid())
 THEN RAISE EXCEPTION 'submission_not_allowed' USING ERRCODE='42501'; END IF;
 IF answer IS NULL OR length(answer::text)>250000 THEN
 RAISE EXCEPTION 'invalid_answer' USING ERRCODE='22023'; END IF;
 SELECT * INTO prev FROM app.submissions s WHERE s.owner_id=auth.uid()
 AND s.client_id=submit_personal_attempt.client_id;
 IF FOUND THEN
   IF prev.item_id<>item OR prev.body<>answer THEN
     RAISE EXCEPTION 'duplicate_client_id_changed_payload' USING ERRCODE='23505';
   END IF;
   RETURN jsonb_build_object('id',prev.id,'submitted_at',prev.submitted_at,'replayed',true);
 END IF;
 INSERT INTO app.submissions(item_id,owner_id,client_id,body)
 VALUES(item,auth.uid(),client_id,answer) RETURNING id INTO sid;
 INSERT INTO app_private.audit_events(actor_id,action,target_id)
 VALUES(auth.uid(),'submission.created',sid);
 RETURN (SELECT jsonb_build_object('id',s.id,'submitted_at',s.submitted_at,'replayed',false)
 FROM app.submissions s WHERE s.id=sid);
END $$;

CREATE FUNCTION api.grade_personal_attempt(submission uuid, expected_version integer,
 points numeric, comments jsonb DEFAULT '{}'::jsonb, release_now boolean DEFAULT false)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE s app.submissions%ROWTYPE; room uuid; current_version integer; new_version integer;
BEGIN
 SELECT * INTO s FROM app.submissions WHERE id=submission FOR UPDATE;
 SELECT a.classroom_id INTO room FROM app.activity_items i
 JOIN app.activities a ON a.id=i.activity_id WHERE i.id=s.item_id;
 IF NOT FOUND OR NOT app_private.manages_classroom(room) THEN
 RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF points IS NULL OR points<0 OR points>100 OR jsonb_typeof(comments)<>'object'
 OR length(comments::text)>30000 THEN RAISE EXCEPTION 'invalid_grade' USING ERRCODE='22023'; END IF;
 SELECT g.version INTO current_version FROM app_private.grades g
 WHERE g.submission_id=submission FOR UPDATE;
 IF coalesce(current_version,0)<>expected_version THEN
 RAISE EXCEPTION 'grade_revision_conflict' USING ERRCODE='40001'; END IF;
 INSERT INTO app_private.grades(submission_id,score,feedback,released_at,version)
 VALUES(submission,points,comments,CASE WHEN release_now THEN now() ELSE NULL END,1)
 ON CONFLICT(submission_id) DO UPDATE SET score=excluded.score, feedback=excluded.feedback,
 released_at=CASE WHEN release_now THEN now() ELSE app_private.grades.released_at END,
 version=app_private.grades.version+1
 RETURNING version INTO new_version;
 INSERT INTO app_private.audit_events(actor_id,action,target_id) VALUES(auth.uid(),'submission.graded',submission);
 RETURN new_version;
END $$;

CREATE FUNCTION api.my_attempt_details(submission uuid) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
DECLARE s app.submissions%ROWTYPE; g app_private.grades%ROWTYPE;
BEGIN
 IF NOT app_private.caller_enabled() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 SELECT * INTO s FROM app.submissions WHERE id=submission AND owner_id=auth.uid();
 IF NOT FOUND THEN RAISE EXCEPTION 'not_found' USING ERRCODE='42501'; END IF;
 SELECT * INTO g FROM app_private.grades WHERE submission_id=submission AND released_at<=now();
 RETURN jsonb_build_object('id',s.id,'item_id',s.item_id,'body',s.body,
 'submitted_at',s.submitted_at,'score',CASE WHEN g.submission_id IS NULL THEN NULL ELSE g.score END,
 'feedback',CASE WHEN g.submission_id IS NULL THEN NULL ELSE g.feedback END);
END $$;

REVOKE ALL ON FUNCTION api.create_classroom(text,jsonb),
 api.change_classroom_membership(uuid,uuid,boolean),
 api.create_problem(uuid,jsonb,jsonb,jsonb,jsonb),
 api.publish_problem(uuid,integer),
 api.list_classroom_problems(uuid),
 api.create_activity(uuid,text,jsonb,timestamptz,timestamptz),
 api.add_activity_problem(uuid,uuid,integer),
 api.publish_activity(uuid,integer),
 api.submit_personal_attempt(uuid,uuid,jsonb),
 api.grade_personal_attempt(uuid,integer,numeric,jsonb,boolean),
 api.my_attempt_details(uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.create_classroom(text,jsonb),
 api.change_classroom_membership(uuid,uuid,boolean),
 api.create_problem(uuid,jsonb,jsonb,jsonb,jsonb),
 api.publish_problem(uuid,integer),
 api.list_classroom_problems(uuid),
 api.create_activity(uuid,text,jsonb,timestamptz,timestamptz),
 api.add_activity_problem(uuid,uuid,integer),
 api.publish_activity(uuid,integer),
 api.submit_personal_attempt(uuid,uuid,jsonb),
 api.grade_personal_attempt(uuid,integer,numeric,jsonb,boolean),
 api.my_attempt_details(uuid) TO authenticated;
COMMIT;
