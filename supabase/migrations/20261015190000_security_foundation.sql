-- M2: ONLY an isolated, empty NEW Supabase staging project.
-- Legacy olympiados role/policies and live Render database must stay untouched.
BEGIN;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='olympiados') THEN
    RAISE EXCEPTION 'Refusing M2 migration: detected legacy olympiados schema';
  END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS api;
CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS app_private;
REVOKE ALL ON SCHEMA api, app, app_private FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA api TO authenticated;
-- Non-exposed app usage required for security_invoker views, not direct Data API exposure.
GRANT USAGE ON SCHEMA app TO authenticated;
GRANT USAGE ON SCHEMA app_private TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA api, app, app_private REVOKE ALL ON TABLES FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA api, app, app_private REVOKE ALL ON FUNCTIONS FROM PUBLIC, anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA api, app, app_private REVOKE ALL ON SEQUENCES FROM PUBLIC, anon, authenticated;

CREATE TABLE app.profiles (
 user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
 email text NOT NULL CHECK (char_length(email) BETWEEN 3 AND 254),
 display_name text NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 100),
 role text NOT NULL DEFAULT 'student' CHECK (role IN ('student','teacher','admin')),
 locale text NOT NULL DEFAULT 'ru' CHECK (locale IN ('ru','en')),
 active boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX profiles_email_lower_idx ON app.profiles(lower(email));

CREATE TABLE app_private.revoked_sessions (
 session_id text PRIMARY KEY CHECK(char_length(session_id) BETWEEN 10 AND 100),
 user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
 revoked_at timestamptz NOT NULL DEFAULT now(),
 reason text NOT NULL DEFAULT 'logout' CHECK (reason IN ('logout','admin','password_change','security'))
);
CREATE INDEX revoked_sessions_user_idx ON app_private.revoked_sessions(user_id);
-- SECURITY DEFINER must be owned by a trusted operator; do not FORCE RLS on
-- app.profiles without adjusting this bypass carefully and re-testing.
CREATE FUNCTION app_private.caller_enabled() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
 SELECT (SELECT auth.uid()) IS NOT NULL
   AND NULLIF((SELECT auth.jwt() ->> 'session_id'), '') IS NOT NULL
   AND EXISTS (SELECT 1 FROM app.profiles p
         WHERE p.user_id = (SELECT auth.uid()) AND p.active)
   AND NOT EXISTS (SELECT 1 FROM app_private.revoked_sessions r
         WHERE r.user_id = (SELECT auth.uid())
           AND r.session_id = (SELECT auth.jwt() ->> 'session_id'));
$$;
CREATE FUNCTION app_private.caller_is_admin() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
 SELECT app_private.caller_enabled() AND EXISTS (
  SELECT 1 FROM app.profiles p WHERE p.user_id=(SELECT auth.uid())
   AND p.role='admin' AND p.active);
$$;

CREATE TABLE app.subjects (
 id text PRIMARY KEY CHECK(id IN ('math','physics','informatics')),
 name jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(name)='object')
);
CREATE TABLE app.subject_memberships (
 subject_id text NOT NULL REFERENCES app.subjects(id),
 user_id uuid NOT NULL REFERENCES app.profiles(user_id) ON DELETE CASCADE,
 active boolean NOT NULL DEFAULT false,
 joined_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(subject_id,user_id)
);
CREATE INDEX subject_memberships_user_idx ON app.subject_memberships(user_id,active);
CREATE TABLE app.topics (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 subject_id text NOT NULL REFERENCES app.subjects(id),
 name jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(name)='object'),
 created_by uuid REFERENCES app.profiles(user_id)
);
CREATE TABLE app.classrooms (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 subject_id text NOT NULL REFERENCES app.subjects(id),
 teacher_id uuid NOT NULL REFERENCES app.profiles(user_id),
 name jsonb NOT NULL CHECK(jsonb_typeof(name)='object'),
 active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX classrooms_teacher_idx ON app.classrooms(teacher_id,active);
CREATE TABLE app.classroom_memberships (
 classroom_id uuid NOT NULL REFERENCES app.classrooms(id) ON DELETE CASCADE,
 student_id uuid NOT NULL REFERENCES app.profiles(user_id) ON DELETE CASCADE,
 joined_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(classroom_id,student_id)
);
CREATE INDEX classroom_memberships_student_idx ON app.classroom_memberships(student_id);
CREATE FUNCTION app_private.manages_classroom(target uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
 SELECT app_private.caller_enabled() AND (
    app_private.caller_is_admin() OR EXISTS (
      SELECT 1 FROM app.classrooms c WHERE c.id=target
       AND c.teacher_id=(SELECT auth.uid()) AND c.active));
$$;
CREATE FUNCTION app_private.has_classroom_access(target uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
 SELECT app_private.manages_classroom(target) OR (
   app_private.caller_enabled() AND EXISTS (
     SELECT 1 FROM app.classroom_memberships m
     JOIN app.classrooms c ON c.id=m.classroom_id
     WHERE m.classroom_id=target AND m.student_id=(SELECT auth.uid()) AND c.active));
$$;

-- Hidden answers/assessment grading are physically separated from ordinary bodies.
CREATE TABLE app.problems (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 classroom_id uuid NOT NULL REFERENCES app.classrooms(id),
 title jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(title)='object'),
 statement jsonb NOT NULL DEFAULT '{}'::jsonb CHECK(jsonb_typeof(statement)='object'),
 version integer NOT NULL DEFAULT 1 CHECK(version>=1),
 published boolean NOT NULL DEFAULT false
);
CREATE INDEX problems_classroom_idx ON app.problems(classroom_id);
CREATE TABLE app_private.problem_secrets (
 problem_id uuid PRIMARY KEY REFERENCES app.problems(id) ON DELETE CASCADE,
 hints jsonb NOT NULL DEFAULT '[]'::jsonb,
 solution jsonb NOT NULL DEFAULT '{}'::jsonb,
 rubric jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE app.activities (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 classroom_id uuid NOT NULL REFERENCES app.classrooms(id),
 kind text NOT NULL CHECK(kind IN ('assignment','session','competition')),
 title jsonb NOT NULL DEFAULT '{}'::jsonb,
 starts_at timestamptz,
 ends_at timestamptz,
 status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','active','ended','archived')),
 version integer NOT NULL DEFAULT 1 CHECK(version>=1),
 CHECK (starts_at IS NULL OR ends_at IS NULL OR ends_at>starts_at)
);
CREATE INDEX activities_classroom_idx ON app.activities(classroom_id,starts_at);
CREATE TABLE app.activity_items (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 activity_id uuid NOT NULL REFERENCES app.activities(id) ON DELETE CASCADE,
 problem_id uuid REFERENCES app.problems(id),
 statement_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
 ordinal integer NOT NULL CHECK(ordinal>=0),
 UNIQUE(activity_id,ordinal)
);
CREATE TABLE app_private.item_snapshot_secrets (
 item_id uuid PRIMARY KEY REFERENCES app.activity_items(id) ON DELETE CASCADE,
 solution_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
 rubric_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE app.submissions (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 item_id uuid NOT NULL REFERENCES app.activity_items(id),
 owner_id uuid NOT NULL REFERENCES app.profiles(user_id),
 client_id uuid NOT NULL,
 body jsonb NOT NULL DEFAULT '{}'::jsonb,
 submitted_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner_id,client_id)
);
CREATE INDEX submissions_item_owner_idx ON app.submissions(item_id,owner_id);
CREATE TABLE app_private.grades (
 submission_id uuid PRIMARY KEY REFERENCES app.submissions(id) ON DELETE CASCADE,
 score numeric(9,2),
 feedback jsonb NOT NULL DEFAULT '{}'::jsonb,
 released_at timestamptz,
 version integer NOT NULL DEFAULT 1 CHECK(version>=1)
);

CREATE TABLE app.training_circles (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 subject_id text NOT NULL REFERENCES app.subjects(id),
 created_by uuid NOT NULL REFERENCES app.profiles(user_id),
 name jsonb NOT NULL CHECK(jsonb_typeof(name)='object'),
 discoverable boolean NOT NULL DEFAULT true,
 archived boolean NOT NULL DEFAULT false,
 locked boolean NOT NULL DEFAULT false,
 version integer NOT NULL DEFAULT 1 CHECK(version>=1)
);
CREATE TABLE app.circle_members (
 circle_id uuid NOT NULL REFERENCES app.training_circles(id) ON DELETE CASCADE,
 user_id uuid NOT NULL REFERENCES app.profiles(user_id) ON DELETE CASCADE,
 role text NOT NULL DEFAULT 'member' CHECK(role IN ('member','facilitator')),
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active')),
 joined_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(circle_id,user_id)
);
CREATE INDEX circle_members_user_idx ON app.circle_members(user_id,status);
CREATE TABLE app.training_cycles (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 owner_id uuid REFERENCES app.profiles(user_id),
 circle_id uuid REFERENCES app.training_circles(id),
 title jsonb NOT NULL DEFAULT '{}'::jsonb,
 start_at timestamptz, end_at timestamptz,
 version integer NOT NULL DEFAULT 1 CHECK(version>=1),
 CHECK ((owner_id IS NULL) <> (circle_id IS NULL))
);
CREATE TABLE app.training_plans (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 cycle_id uuid NOT NULL REFERENCES app.training_cycles(id) ON DELETE CASCADE,
 owner_id uuid NOT NULL REFERENCES app.profiles(user_id) ON DELETE CASCADE,
 goal text NOT NULL DEFAULT '' CHECK(char_length(goal)<=8000),
 review text NOT NULL DEFAULT '' CHECK(char_length(review)<=16000),
 next_step text NOT NULL DEFAULT '' CHECK(char_length(next_step)<=8000),
 context jsonb NOT NULL DEFAULT '{}'::jsonb,
 version integer NOT NULL DEFAULT 1 CHECK(version>=1),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(cycle_id,owner_id)
);
CREATE INDEX training_plans_owner_idx ON app.training_plans(owner_id,created_at);

CREATE TABLE app_private.account_invitations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 token_hash text NOT NULL UNIQUE CHECK(char_length(token_hash)=64),
 intended_email text NOT NULL CHECK(char_length(intended_email)<=254),
 intended_role text NOT NULL CHECK(intended_role IN ('student','teacher','admin')),
 classroom_id uuid REFERENCES app.classrooms(id),
 created_by uuid NOT NULL REFERENCES app.profiles(user_id),
 expires_at timestamptz NOT NULL, consumed_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app.enrollment_invitations (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 classroom_id uuid NOT NULL REFERENCES app.classrooms(id),
 student_id uuid NOT NULL REFERENCES app.profiles(user_id),
 token_hash text NOT NULL UNIQUE CHECK(char_length(token_hash)=64),
 created_by uuid NOT NULL REFERENCES app.profiles(user_id),
 expires_at timestamptz NOT NULL,
 consumed_at timestamptz
);
CREATE TABLE app_private.audit_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 actor_id uuid REFERENCES app.profiles(user_id),
 action text NOT NULL, target_id uuid,
 created_at timestamptz NOT NULL DEFAULT now()
);

-- Default-deny: every table receives RLS and browser grants are revoked.
DO $$ DECLARE t record; BEGIN
 FOR t IN SELECT n.nspname,c.relname FROM pg_class c
   JOIN pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname IN ('app','app_private') AND c.relkind IN ('r','p') LOOP
  EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',t.nspname,t.relname);
  EXECUTE format('REVOKE ALL ON TABLE %I.%I FROM PUBLIC, anon, authenticated',t.nspname,t.relname);
 END LOOP;
END $$;
GRANT SELECT ON app.profiles,app.subjects,app.subject_memberships,
 app.classrooms,app.classroom_memberships,app.training_cycles,app.training_plans TO authenticated;
CREATE POLICY own_profile ON app.profiles FOR SELECT TO authenticated
 USING (user_id=(SELECT auth.uid()) AND (SELECT app_private.caller_enabled()));
CREATE POLICY subjects_for_enabled ON app.subjects FOR SELECT TO authenticated
 USING ((SELECT app_private.caller_enabled()));
CREATE POLICY own_subject_memberships ON app.subject_memberships FOR SELECT TO authenticated
 USING (user_id=(SELECT auth.uid()) AND (SELECT app_private.caller_enabled()));
CREATE POLICY current_classrooms ON app.classrooms FOR SELECT TO authenticated
 USING (app_private.has_classroom_access(id));
CREATE POLICY permitted_classroom_memberships ON app.classroom_memberships FOR SELECT TO authenticated
 USING ((student_id=(SELECT auth.uid()) AND (SELECT app_private.caller_enabled()))
    OR app_private.manages_classroom(classroom_id));
CREATE POLICY private_cycles_only ON app.training_cycles FOR SELECT TO authenticated
 USING (owner_id=(SELECT auth.uid()) AND (SELECT app_private.caller_enabled()));
CREATE POLICY owner_plans_only ON app.training_plans FOR SELECT TO authenticated
 USING (owner_id=(SELECT auth.uid()) AND (SELECT app_private.caller_enabled()));

REVOKE ALL ON FUNCTION app_private.caller_enabled(),app_private.caller_is_admin(),
 app_private.manages_classroom(uuid),app_private.has_classroom_access(uuid)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION app_private.caller_enabled(),app_private.caller_is_admin(),
 app_private.manages_classroom(uuid),app_private.has_classroom_access(uuid) TO authenticated;

-- Caller-invoker view means even an admin must pass underlying student RLS.
CREATE VIEW api.my_profile WITH (security_invoker=true) AS
 SELECT user_id,display_name,role,locale,active,created_at FROM app.profiles;
CREATE VIEW api.subjects WITH (security_invoker=true) AS
 SELECT id,name FROM app.subjects;
CREATE VIEW api.my_subjects WITH (security_invoker=true) AS
 SELECT subject_id,active,joined_at FROM app.subject_memberships;
CREATE VIEW api.my_classrooms WITH (security_invoker=true) AS
 SELECT id,subject_id,teacher_id,name,active,created_at FROM app.classrooms;
CREATE VIEW api.my_training_plans WITH (security_invoker=true) AS
 SELECT id,cycle_id,goal,review,next_step,context,version,created_at,updated_at FROM app.training_plans;
GRANT SELECT ON api.my_profile,api.subjects,api.my_subjects,
 api.my_classrooms,api.my_training_plans TO authenticated;

INSERT INTO app.subjects(id,name) VALUES
 ('math','{"en":"Mathematics","ru":"Математика"}'::jsonb),
 ('physics','{"en":"Physics","ru":"Физика"}'::jsonb),
 ('informatics','{"en":"Informatics","ru":"Информатика"}'::jsonb);
COMMENT ON SCHEMA api IS 'Only custom Supabase Data API schema for replacement app';
COMMENT ON SCHEMA app IS 'Non-exposed domain tables';
COMMENT ON SCHEMA app_private IS 'Never expose: tokens, scores, hidden answers, audit';
COMMIT;
