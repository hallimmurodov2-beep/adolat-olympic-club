-- M3 continuation: invite acceptance requires a verified Supabase Auth identity.
-- No public account creation or privilege-changing table grants.
BEGIN;
CREATE FUNCTION api.accept_registration(registration_token text, display_name text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE invitation app_private.account_invitations%ROWTYPE;
        usr auth.users%ROWTYPE;
BEGIN
 IF auth.uid() IS NULL OR NULLIF(auth.jwt()->>'session_id','') IS NULL
 OR registration_token IS NULL OR length(registration_token)<>64
 OR display_name IS NULL OR length(trim(display_name)) NOT BETWEEN 2 AND 100
 THEN RAISE EXCEPTION 'invalid_registration' USING ERRCODE='42501'; END IF;
 SELECT * INTO usr FROM auth.users WHERE id=auth.uid() AND email_confirmed_at IS NOT NULL;
 IF NOT FOUND THEN RAISE EXCEPTION 'email_unverified' USING ERRCODE='42501'; END IF;
 SELECT * INTO invitation FROM app_private.account_invitations
 WHERE token_hash=encode(extensions.digest(registration_token,'sha256'),'hex')
 AND consumed_at IS NULL AND expires_at>now() FOR UPDATE;
 IF NOT FOUND OR invitation.intended_email<>lower(usr.email)
 OR EXISTS(SELECT 1 FROM app.profiles WHERE user_id=auth.uid())
 THEN RAISE EXCEPTION 'invalid_invitation' USING ERRCODE='42501'; END IF;
 IF invitation.classroom_id IS NOT NULL AND NOT EXISTS(
  SELECT 1 FROM app.classrooms WHERE id=invitation.classroom_id AND active)
 THEN RAISE EXCEPTION 'classroom_inactive' USING ERRCODE='42501'; END IF;
 INSERT INTO app.profiles(user_id,email,display_name,role,active)
 VALUES(usr.id,lower(usr.email),trim(display_name),invitation.intended_role,true);
 IF invitation.classroom_id IS NOT NULL THEN
  INSERT INTO app.classroom_memberships(classroom_id,student_id)
  VALUES(invitation.classroom_id,usr.id);
 END IF;
 UPDATE app_private.account_invitations SET consumed_at=now() WHERE id=invitation.id;
 UPDATE app_private.provisioning_outbox SET state='accepted',auth_user_id=usr.id,updated_at=now()
 WHERE invitation_id=invitation.id;
 INSERT INTO app_private.audit_events(actor_id,action,target_id)
 VALUES(usr.id,'invitation.accepted',invitation.id);
 RETURN jsonb_build_object('user_id',usr.id,'role',invitation.intended_role,'active',true);
END $$;

CREATE FUNCTION api.issue_classroom_enrollment(room uuid, student uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE plain_token text; iid uuid;
BEGIN
 IF NOT app_private.manages_classroom(room) OR NOT EXISTS(
  SELECT 1 FROM app.profiles WHERE user_id=student AND active AND role='student')
 OR NOT EXISTS(SELECT 1 FROM app.classrooms WHERE id=room AND active)
 OR EXISTS(SELECT 1 FROM app.classroom_memberships
  WHERE classroom_id=room AND student_id=student)
 THEN RAISE EXCEPTION 'enrollment_forbidden' USING ERRCODE='42501'; END IF;
 plain_token:=encode(extensions.gen_random_bytes(32),'hex');
 INSERT INTO app.enrollment_invitations(classroom_id,student_id,token_hash,created_by,expires_at)
 VALUES(room,student,encode(extensions.digest(plain_token,'sha256'),'hex'),auth.uid(),now()+interval '7 days')
 RETURNING id INTO iid;
 RETURN jsonb_build_object('id',iid,'token',plain_token,'expires_at',now()+interval '7 days');
END $$;

CREATE FUNCTION api.accept_classroom_enrollment(plain_token text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE invitation app.enrollment_invitations%ROWTYPE;
BEGIN
 IF NOT app_private.caller_enabled() OR plain_token IS NULL OR length(plain_token)<>64
 OR NOT EXISTS(SELECT 1 FROM app.profiles WHERE user_id=auth.uid() AND role='student')
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 SELECT * INTO invitation FROM app.enrollment_invitations
 WHERE token_hash=encode(extensions.digest(plain_token,'sha256'),'hex')
  AND student_id=auth.uid() AND consumed_at IS NULL AND expires_at>now() FOR UPDATE;
 IF NOT FOUND OR NOT EXISTS(SELECT 1 FROM app.classrooms
  WHERE id=invitation.classroom_id AND active)
 THEN RAISE EXCEPTION 'invalid_invitation' USING ERRCODE='42501'; END IF;
 INSERT INTO app.classroom_memberships(classroom_id,student_id)
 VALUES(invitation.classroom_id,auth.uid())
 ON CONFLICT DO NOTHING;
 UPDATE app.enrollment_invitations SET consumed_at=now() WHERE id=invitation.id;
 RETURN invitation.classroom_id;
END $$;

REVOKE ALL ON FUNCTION api.accept_registration(text,text),
 api.issue_classroom_enrollment(uuid,uuid),
 api.accept_classroom_enrollment(text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.accept_registration(text,text),
 api.issue_classroom_enrollment(uuid,uuid),
 api.accept_classroom_enrollment(text) TO authenticated;
COMMIT;
