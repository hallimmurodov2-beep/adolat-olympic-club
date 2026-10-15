-- M3 prototype: identity, authenticated bootstrap and controlled account lifecycle.
-- Applied ONLY to an isolated serverless Supabase project after M2.
BEGIN;
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='olympiados') THEN
   RAISE EXCEPTION 'Legacy olympiados project: abort M3';
 END IF;
END $$;

CREATE TABLE app_private.provisioning_outbox (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 invitation_id uuid NOT NULL REFERENCES app_private.account_invitations(id),
 auth_user_id uuid REFERENCES auth.users(id),
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','auth_created','accepted','failed','revoked')),
 error_code text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(invitation_id)
);
ALTER TABLE app_private.provisioning_outbox ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app_private.provisioning_outbox FROM PUBLIC, anon, authenticated;

-- No arbitrary caller-selected identity: all api entry points derive identity from JWT.
CREATE FUNCTION api.bootstrap() RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
DECLARE p record; clubs jsonb; subj jsonb;
BEGIN
 IF NOT app_private.caller_enabled() THEN
   RAISE EXCEPTION 'unauthenticated' USING ERRCODE='42501';
 END IF;
 SELECT user_id,display_name,role,locale,active INTO p FROM app.profiles
   WHERE user_id=auth.uid();
 SELECT COALESCE(jsonb_agg(jsonb_build_object('id',id,'name',name) ORDER BY id),'[]'::jsonb)
   INTO subj FROM app.subjects;
 RETURN jsonb_build_object(
   'user',jsonb_build_object('id',p.user_id,'display_name',p.display_name,'role',p.role,'locale',p.locale,'active',p.active),
   'subjects',subj,
   'can_train',EXISTS(SELECT 1 FROM app.subject_memberships sm
      WHERE sm.user_id=auth.uid() AND sm.subject_id='informatics' AND sm.active),
   'settings',jsonb_build_object('timezone','Asia/Dushanbe','name',
      jsonb_build_object('en','Adolat Olympic Club','ru','Adolat Olympic Club')),
   'server_now',(extract(epoch FROM clock_timestamp())*1000)::bigint);
END $$;
CREATE FUNCTION api.update_my_profile(new_name text, new_locale text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE p app.profiles%ROWTYPE;
BEGIN
 IF NOT app_private.caller_enabled() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF new_name IS NULL OR length(trim(new_name)) NOT BETWEEN 2 AND 100
    OR new_locale NOT IN ('en','ru') THEN
   RAISE EXCEPTION 'invalid_input' USING ERRCODE='22023';
 END IF;
 UPDATE app.profiles SET display_name=trim(new_name),locale=new_locale,updated_at=now()
 WHERE user_id=auth.uid() RETURNING * INTO p;
 RETURN jsonb_build_object('id',p.user_id,'display_name',p.display_name,'locale',p.locale,
 'role',p.role,'active',p.active);
END $$;

CREATE FUNCTION api.revoke_my_session() RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE sid text := auth.jwt()->>'session_id';
BEGIN
 IF NOT app_private.caller_enabled() OR sid IS NULL OR length(sid)<10 THEN
    RAISE EXCEPTION 'unauthenticated' USING ERRCODE='42501';
 END IF;
 INSERT INTO app_private.revoked_sessions(session_id,user_id,reason)
 VALUES (sid,auth.uid(),'logout') ON CONFLICT(session_id) DO NOTHING;
 RETURN true;
END $$;

CREATE FUNCTION api.admin_set_subject_eligibility(target uuid, subject text, enabled boolean) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NOT app_private.caller_is_admin() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF subject NOT IN ('math','physics','informatics')
  OR NOT EXISTS(SELECT 1 FROM app.profiles WHERE user_id=target AND role='student' AND active)
 THEN RAISE EXCEPTION 'invalid_subject_or_user' USING ERRCODE='22023'; END IF;
 INSERT INTO app.subject_memberships(subject_id,user_id,active)
 VALUES(subject,target,enabled)
 ON CONFLICT(subject_id,user_id) DO UPDATE SET active=excluded.active;
 INSERT INTO app_private.audit_events(actor_id,action,target_id)
 VALUES(auth.uid(),'subject.eligibility_changed',target);
 RETURN true;
END $$;

-- Two distinct workflows: only privileged staff can issue registration links.
-- Tokens are cryptographically random. The digest is stored; plaintext is returned ONCE.
-- An Edge provisioning service must bind confirmed email and consume the invite before activation.
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;
CREATE FUNCTION api.issue_registration_invitation(
 target_email text, intended_role text, target_classroom uuid DEFAULT NULL
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE token text; iid uuid; role_name text;
BEGIN
 IF NOT app_private.caller_enabled() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 SELECT role INTO role_name FROM app.profiles WHERE user_id=auth.uid();
 IF role_name NOT IN ('admin','teacher') OR
   (role_name='teacher' AND (intended_role <> 'student' OR target_classroom IS NULL))
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF target_classroom IS NOT NULL AND
   (intended_role <> 'student' OR NOT app_private.manages_classroom(target_classroom))
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 IF intended_role NOT IN ('student','teacher','admin')
   OR target_email IS NULL OR length(trim(target_email)) NOT BETWEEN 3 AND 254
   OR position('@' IN target_email)<2
 THEN RAISE EXCEPTION 'invalid_input' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM app.profiles WHERE lower(email)=lower(trim(target_email)))
 THEN RAISE EXCEPTION 'account_exists' USING ERRCODE='23505'; END IF;
 token := encode(extensions.gen_random_bytes(32),'hex');
 INSERT INTO app_private.account_invitations(token_hash,intended_email,intended_role,classroom_id,created_by,expires_at)
 VALUES(encode(extensions.digest(token,'sha256'),'hex'),lower(trim(target_email)),intended_role,
   target_classroom,auth.uid(),now()+interval '7 days') RETURNING id INTO iid;
 INSERT INTO app_private.provisioning_outbox(invitation_id) VALUES(iid);
 INSERT INTO app_private.audit_events(actor_id,action,target_id) VALUES(auth.uid(),'invitation.created',iid);
 RETURN jsonb_build_object('id',iid,'token',token,'expires_at',now()+interval '7 days');
END $$;

-- Provisioning must be performed by an authenticated, audited operator/Edge
-- service; not granted to authenticated, anon, or public.
CREATE FUNCTION app_private.complete_registration(
 registration_token text, verified_user uuid, confirmed_email text, new_display_name text
) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE invitation app_private.account_invitations%ROWTYPE;
BEGIN
 IF current_user <> 'postgres' THEN
  RAISE EXCEPTION 'operator_only' USING ERRCODE='42501';
 END IF;
 SELECT * INTO invitation FROM app_private.account_invitations
 WHERE token_hash=encode(extensions.digest(registration_token,'sha256'),'hex')
   AND consumed_at IS NULL AND expires_at>now() FOR UPDATE;
 IF NOT FOUND OR lower(trim(confirmed_email))<>invitation.intended_email
   OR NOT EXISTS(SELECT 1 FROM auth.users WHERE id=verified_user AND
     lower(email)=invitation.intended_email AND email_confirmed_at IS NOT NULL)
 THEN RAISE EXCEPTION 'invalid_invitation' USING ERRCODE='42501'; END IF;
 INSERT INTO app.profiles(user_id,email,display_name,role,active)
 VALUES(verified_user,invitation.intended_email,trim(new_display_name),invitation.intended_role,true);
 IF invitation.classroom_id IS NOT NULL THEN
   INSERT INTO app.classroom_memberships(classroom_id,student_id)
   VALUES(invitation.classroom_id,verified_user);
 END IF;
 UPDATE app_private.account_invitations SET consumed_at=now() WHERE id=invitation.id;
 UPDATE app_private.provisioning_outbox SET state='accepted',auth_user_id=verified_user,updated_at=now()
 WHERE invitation_id=invitation.id;
 RETURN verified_user;
END $$;

-- Provisioning is intentionally unavailable until M3 Auth Admin Edge verification.
REVOKE ALL ON FUNCTION app_private.complete_registration(text,uuid,text,text)
 FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION api.bootstrap(),api.update_my_profile(text,text),
 api.revoke_my_session(),api.admin_set_subject_eligibility(uuid,text,boolean),
 api.issue_registration_invitation(text,text,uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.bootstrap(),api.update_my_profile(text,text),
 api.revoke_my_session(),api.admin_set_subject_eligibility(uuid,text,boolean),
 api.issue_registration_invitation(text,text,uuid) TO authenticated;
COMMIT;
