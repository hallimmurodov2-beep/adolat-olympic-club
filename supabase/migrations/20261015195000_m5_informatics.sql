-- M5: owner-only Informatics goal/practice and controlled circle workflows.
-- All browser mutations go through reviewed SECURITY DEFINER domain functions.
BEGIN;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='olympiados')
 THEN RAISE EXCEPTION 'Legacy project: refusing M5'; END IF; END $$;

CREATE TABLE app.training_items (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 plan_id uuid NOT NULL REFERENCES app.training_plans(id) ON DELETE CASCADE,
 owner_id uuid NOT NULL REFERENCES app.profiles(user_id) ON DELETE CASCADE,
 client_id uuid NOT NULL,
 title text NOT NULL CHECK(length(title) BETWEEN 1 AND 300),
 done boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner_id,client_id)
);
CREATE INDEX training_items_plan_idx ON app.training_items(plan_id);
CREATE TABLE app.practice_entries (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 item_id uuid NOT NULL REFERENCES app.training_items(id) ON DELETE CASCADE,
 owner_id uuid NOT NULL REFERENCES app.profiles(user_id) ON DELETE CASCADE,
 client_id uuid NOT NULL,
 note text NOT NULL DEFAULT '' CHECK(length(note)<=10000),
 minutes integer NOT NULL CHECK(minutes BETWEEN 0 AND 720),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(owner_id,client_id)
);
CREATE INDEX practice_entries_item_idx ON app.practice_entries(item_id,created_at);
CREATE TABLE app.peer_posts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 cycle_id uuid NOT NULL REFERENCES app.training_cycles(id) ON DELETE CASCADE,
 circle_id uuid NOT NULL REFERENCES app.training_circles(id) ON DELETE CASCADE,
 author_id uuid NOT NULL REFERENCES app.profiles(user_id),
 content text NOT NULL CHECK(length(content) BETWEEN 1 AND 4000),
 hidden boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX peer_posts_cycle_idx ON app.peer_posts(cycle_id,created_at);
CREATE TABLE app_private.moderation_reports (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 post_id uuid NOT NULL REFERENCES app.peer_posts(id),
 reporter_id uuid NOT NULL REFERENCES app.profiles(user_id),
 reason text NOT NULL CHECK(length(reason) BETWEEN 10 AND 1500),
 resolved_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(post_id,reporter_id)
);
DO $$ DECLARE r record; BEGIN
 FOR r IN SELECT tablename FROM pg_tables WHERE schemaname IN ('app','app_private')
 AND tablename IN ('training_items','practice_entries','peer_posts','moderation_reports')
 LOOP
   EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',
      CASE WHEN r.tablename='moderation_reports' THEN 'app_private' ELSE 'app' END,r.tablename);
   EXECUTE format('REVOKE ALL ON TABLE %I.%I FROM PUBLIC,anon,authenticated',
      CASE WHEN r.tablename='moderation_reports' THEN 'app_private' ELSE 'app' END,r.tablename);
 END LOOP;
END $$;

CREATE FUNCTION app_private.can_train() RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT app_private.caller_enabled() AND EXISTS(
 SELECT 1 FROM app.profiles p JOIN app.subject_memberships sm ON sm.user_id=p.user_id
 WHERE p.user_id=auth.uid() AND p.role='student' AND sm.subject_id='informatics' AND sm.active);
$$;
CREATE FUNCTION app_private.is_active_circle_member(cid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT app_private.can_train() AND EXISTS(
 SELECT 1 FROM app.circle_members cm JOIN app.training_circles c ON c.id=cm.circle_id
 WHERE cm.circle_id=cid AND cm.user_id=auth.uid()
 AND cm.status='active' AND NOT c.archived);
$$;
CREATE FUNCTION app_private.is_circle_facilitator(cid uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT app_private.is_active_circle_member(cid) AND EXISTS(
 SELECT 1 FROM app.circle_members cm WHERE cm.circle_id=cid
 AND cm.user_id=auth.uid() AND cm.role='facilitator');
$$;

CREATE FUNCTION api.create_personal_cycle(cycle_title jsonb) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE cid uuid;
BEGIN
 IF NOT app_private.can_train() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF jsonb_typeof(cycle_title)<>'object' OR length(cycle_title::text)>3000 THEN
 RAISE EXCEPTION 'invalid_title' USING ERRCODE='22023'; END IF;
 INSERT INTO app.training_cycles(owner_id,title) VALUES(auth.uid(),cycle_title) RETURNING id INTO cid;
 RETURN cid;
END $$;
CREATE FUNCTION api.save_personal_plan(cycle uuid, plan_goal text, plan_review text,
 plan_next_step text, plan_context jsonb, expected_version integer DEFAULT 0)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE prev app.training_plans%ROWTYPE; next_version integer; plan_id uuid;
BEGIN
 IF NOT app_private.can_train() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM app.training_cycles WHERE id=cycle AND owner_id=auth.uid() FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'not_owner' USING ERRCODE='42501'; END IF;
 IF plan_goal IS NULL OR length(plan_goal)>8000 OR plan_review IS NULL OR length(plan_review)>16000
 OR plan_next_step IS NULL OR length(plan_next_step)>8000 OR jsonb_typeof(plan_context)<>'object'
 OR length(plan_context::text)>20000
 THEN RAISE EXCEPTION 'invalid_input' USING ERRCODE='22023'; END IF;
 SELECT * INTO prev FROM app.training_plans WHERE cycle_id=cycle AND owner_id=auth.uid() FOR UPDATE;
 IF FOUND THEN
   IF prev.version<>expected_version THEN RAISE EXCEPTION 'revision_conflict' USING ERRCODE='40001'; END IF;
   UPDATE app.training_plans SET goal=plan_goal,review=plan_review,next_step=plan_next_step,
   context=plan_context,version=version+1,updated_at=now() WHERE id=prev.id
   RETURNING id,version INTO plan_id,next_version;
 ELSE
   IF expected_version<>0 THEN RAISE EXCEPTION 'revision_conflict' USING ERRCODE='40001'; END IF;
   INSERT INTO app.training_plans(cycle_id,owner_id,goal,review,next_step,context)
   VALUES(cycle,auth.uid(),plan_goal,plan_review,plan_next_step,plan_context)
   RETURNING id,version INTO plan_id,next_version;
 END IF;
 RETURN jsonb_build_object('id',plan_id,'version',next_version);
END $$;

CREATE FUNCTION api.add_training_item(plan uuid, client_id uuid, item_title text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE iid uuid; existing app.training_items%ROWTYPE;
BEGIN
 IF NOT app_private.can_train() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM app.training_plans WHERE id=plan AND owner_id=auth.uid() FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'not_owner' USING ERRCODE='42501'; END IF;
 IF item_title IS NULL OR length(trim(item_title)) NOT BETWEEN 1 AND 300 THEN
 RAISE EXCEPTION 'invalid_title' USING ERRCODE='22023'; END IF;
 SELECT * INTO existing FROM app.training_items WHERE owner_id=auth.uid()
 AND app.training_items.client_id=add_training_item.client_id;
 IF FOUND THEN
  IF existing.plan_id<>plan OR existing.title<>trim(item_title) THEN
   RAISE EXCEPTION 'client_id_conflict' USING ERRCODE='23505'; END IF;
  RETURN existing.id;
 END IF;
 INSERT INTO app.training_items(plan_id,owner_id,client_id,title)
 VALUES(plan,auth.uid(),client_id,trim(item_title)) RETURNING id INTO iid;
 RETURN iid;
END $$;
CREATE FUNCTION api.log_practice(item uuid, client_id uuid, practice_minutes integer, practice_note text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE eid uuid; existing app.practice_entries%ROWTYPE;
BEGIN
 IF NOT app_private.can_train() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM app.training_items WHERE id=item AND owner_id=auth.uid() FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'not_owner' USING ERRCODE='42501'; END IF;
 IF practice_minutes NOT BETWEEN 0 AND 720 OR practice_note IS NULL OR length(practice_note)>10000
 THEN RAISE EXCEPTION 'invalid_input' USING ERRCODE='22023'; END IF;
 SELECT * INTO existing FROM app.practice_entries WHERE owner_id=auth.uid()
 AND app.practice_entries.client_id=log_practice.client_id;
 IF FOUND THEN
  IF existing.item_id<>item OR existing.minutes<>practice_minutes OR existing.note<>practice_note
  THEN RAISE EXCEPTION 'client_id_conflict' USING ERRCODE='23505'; END IF;
  RETURN existing.id;
 END IF;
 INSERT INTO app.practice_entries(item_id,owner_id,client_id,minutes,note)
 VALUES(item,auth.uid(),client_id,practice_minutes,practice_note) RETURNING id INTO eid;
 RETURN eid;
END $$;

CREATE FUNCTION api.create_training_circle(circle_name jsonb, is_discoverable boolean DEFAULT true)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE cid uuid;
BEGIN
 IF NOT app_private.can_train() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF jsonb_typeof(circle_name)<>'object' OR length(circle_name::text)>3000
 THEN RAISE EXCEPTION 'invalid_name' USING ERRCODE='22023'; END IF;
 INSERT INTO app.training_circles(subject_id,created_by,name,discoverable)
 VALUES('informatics',auth.uid(),circle_name,is_discoverable) RETURNING id INTO cid;
 INSERT INTO app.circle_members(circle_id,user_id,role,status)
 VALUES(cid,auth.uid(),'facilitator','active');
 RETURN cid;
END $$;
CREATE FUNCTION api.request_circle_join(cid uuid) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE circle app.training_circles%ROWTYPE; member app.circle_members%ROWTYPE;
BEGIN
 IF NOT app_private.can_train() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 SELECT * INTO circle FROM app.training_circles WHERE id=cid FOR UPDATE;
 IF NOT FOUND OR circle.archived OR circle.locked OR NOT circle.discoverable
 THEN RAISE EXCEPTION 'circle_unavailable' USING ERRCODE='42501'; END IF;
 INSERT INTO app.circle_members(circle_id,user_id,role,status)
 VALUES(cid,auth.uid(),'member','pending') ON CONFLICT DO NOTHING;
 SELECT * INTO member FROM app.circle_members WHERE circle_id=cid AND user_id=auth.uid();
 RETURN member.status;
END $$;
CREATE FUNCTION api.approve_circle_join(cid uuid, target uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 PERFORM 1 FROM app.training_circles WHERE id=cid AND NOT archived AND NOT locked FOR UPDATE;
 IF NOT FOUND OR NOT app_private.is_circle_facilitator(cid)
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM app.subject_memberships
 WHERE subject_id='informatics' AND user_id=target AND active)
 THEN RAISE EXCEPTION 'not_eligible' USING ERRCODE='42501'; END IF;
 UPDATE app.circle_members SET status='active' WHERE circle_id=cid AND user_id=target AND status='pending';
 IF NOT FOUND THEN RAISE EXCEPTION 'no_pending_request' USING ERRCODE='22023'; END IF;
 RETURN true;
END $$;
CREATE FUNCTION api.leave_training_circle(cid uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE m app.circle_members%ROWTYPE;
BEGIN
 PERFORM 1 FROM app.training_circles WHERE id=cid FOR UPDATE;
 IF NOT FOUND OR NOT app_private.is_active_circle_member(cid)
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 SELECT * INTO m FROM app.circle_members WHERE circle_id=cid AND user_id=auth.uid() FOR UPDATE;
 IF m.role='facilitator' AND NOT EXISTS(SELECT 1 FROM app.circle_members
 WHERE circle_id=cid AND user_id<>auth.uid() AND role='facilitator' AND status='active')
 THEN RAISE EXCEPTION 'last_facilitator' USING ERRCODE='23514'; END IF;
 DELETE FROM app.circle_members WHERE circle_id=cid AND user_id=auth.uid();
 RETURN true;
END $$;

CREATE FUNCTION api.create_circle_cycle(cid uuid, cycle_title jsonb, debrief_at timestamptz)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE new_id uuid;
BEGIN
 IF NOT app_private.is_circle_facilitator(cid) THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF jsonb_typeof(cycle_title)<>'object' OR debrief_at IS NULL OR debrief_at<=now()
 THEN RAISE EXCEPTION 'invalid_cycle' USING ERRCODE='22023'; END IF;
 INSERT INTO app.training_cycles(circle_id,title,end_at)
 VALUES(cid,cycle_title,debrief_at) RETURNING id INTO new_id;
 RETURN new_id;
END $$;
CREATE FUNCTION api.post_cycle_debrief(cycle uuid, post_text text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE cy app.training_cycles%ROWTYPE; post_id uuid;
BEGIN
 SELECT * INTO cy FROM app.training_cycles WHERE id=cycle FOR UPDATE;
 IF NOT FOUND OR cy.circle_id IS NULL OR cy.end_at IS NULL OR clock_timestamp()<cy.end_at
 OR NOT app_private.is_active_circle_member(cy.circle_id)
 OR EXISTS(SELECT 1 FROM app.training_circles
  WHERE id=cy.circle_id AND (locked OR archived))
 THEN RAISE EXCEPTION 'discussion_not_open' USING ERRCODE='42501'; END IF;
 -- Live competitions prohibit freeform peer discussion.
 IF EXISTS(SELECT 1 FROM app.activities a JOIN app.classroom_memberships m
 ON a.classroom_id=m.classroom_id WHERE m.student_id=auth.uid()
 AND a.kind='competition' AND a.status IN ('published','active')
 AND clock_timestamp()>=a.starts_at AND clock_timestamp()<a.ends_at)
 THEN RAISE EXCEPTION 'competition_discussion_blocked' USING ERRCODE='42501'; END IF;
 IF post_text IS NULL OR length(trim(post_text)) NOT BETWEEN 1 AND 4000
 THEN RAISE EXCEPTION 'invalid_post' USING ERRCODE='22023'; END IF;
 INSERT INTO app.peer_posts(cycle_id,circle_id,author_id,content)
 VALUES(cycle,cy.circle_id,auth.uid(),trim(post_text)) RETURNING id INTO post_id;
 RETURN post_id;
END $$;
CREATE FUNCTION api.circle_debrief_posts(cycle uuid) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
DECLARE cy app.training_cycles%ROWTYPE;
BEGIN
 SELECT * INTO cy FROM app.training_cycles WHERE id=cycle;
 IF NOT FOUND OR cy.circle_id IS NULL OR cy.end_at IS NULL OR now()<cy.end_at
 OR NOT app_private.is_active_circle_member(cy.circle_id)
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 RETURN (SELECT coalesce(jsonb_agg(jsonb_build_object('id',p.id,'content',p.content,
 'author_id',p.author_id,'created_at',p.created_at) ORDER BY p.created_at),'[]'::jsonb)
 FROM app.peer_posts p WHERE p.cycle_id=cycle AND NOT p.hidden);
END $$;

-- Private plans/notes never become visible to facilitators through these APIs.
CREATE FUNCTION api.my_practice_items(plan uuid) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NOT app_private.can_train() OR NOT EXISTS(
 SELECT 1 FROM app.training_plans WHERE id=plan AND owner_id=auth.uid())
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 RETURN (SELECT coalesce(jsonb_agg(jsonb_build_object('id',i.id,'title',i.title,
 'done',i.done,'created_at',i.created_at) ORDER BY i.created_at),'[]'::jsonb)
 FROM app.training_items i WHERE i.plan_id=plan AND i.owner_id=auth.uid());
END $$;
-- Deny direct base-table writes/reads for all new tables. Every RPC itself checks
-- live subject eligibility and ownership/membership, regardless of JWT staleness.
REVOKE ALL ON FUNCTION app_private.can_train(),
 app_private.is_active_circle_member(uuid),app_private.is_circle_facilitator(uuid)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION app_private.can_train(),
 app_private.is_active_circle_member(uuid),app_private.is_circle_facilitator(uuid)
 TO authenticated;
REVOKE ALL ON FUNCTION api.create_personal_cycle(jsonb),
 api.save_personal_plan(uuid,text,text,text,jsonb,integer),
 api.add_training_item(uuid,uuid,text),api.log_practice(uuid,uuid,integer,text),
 api.create_training_circle(jsonb,boolean),api.request_circle_join(uuid),
 api.approve_circle_join(uuid,uuid),api.leave_training_circle(uuid),
 api.create_circle_cycle(uuid,jsonb,timestamptz),
 api.post_cycle_debrief(uuid,text),api.circle_debrief_posts(uuid),api.my_practice_items(uuid)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.create_personal_cycle(jsonb),
 api.save_personal_plan(uuid,text,text,text,jsonb,integer),
 api.add_training_item(uuid,uuid,text),api.log_practice(uuid,uuid,integer,text),
 api.create_training_circle(jsonb,boolean),api.request_circle_join(uuid),
 api.approve_circle_join(uuid,uuid),api.leave_training_circle(uuid),
 api.create_circle_cycle(uuid,jsonb,timestamptz),
 api.post_cycle_debrief(uuid,text),api.circle_debrief_posts(uuid),api.my_practice_items(uuid)
 TO authenticated;
COMMIT;
