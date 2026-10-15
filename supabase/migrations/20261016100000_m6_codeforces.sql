-- M6 Codeforces: private link, separate consent and administrator approval.
-- Staging only; do not use with the legacy olympiados database.
BEGIN;
DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_namespace WHERE nspname='olympiados')
THEN RAISE EXCEPTION 'Legacy project detected; refusing M6'; END IF; END $$;
CREATE TABLE app_private.external_accounts (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 owner_id uuid NOT NULL UNIQUE REFERENCES app.profiles(user_id) ON DELETE CASCADE,
 handle text NOT NULL CHECK(handle ~ '^[A-Za-z0-9_.-]{3,24}$'),
 handle_key text NOT NULL CHECK(handle_key ~ '^[a-z0-9_.-]{3,24}$'),
 consent_at timestamptz NOT NULL DEFAULT now(),
 opted_in boolean NOT NULL DEFAULT false,
 approval_status text NOT NULL DEFAULT 'pending_validation'
 CHECK (approval_status IN ('pending_validation','pending_approval','approved','rejected','invalid_handle')),
 approved_handle_key text UNIQUE,
 approved_by uuid REFERENCES app.profiles(user_id),
 approved_at timestamptz,
 version integer NOT NULL DEFAULT 1 CHECK(version>=1),
 next_refresh_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK ((approval_status='approved')=(approved_handle_key IS NOT NULL))
);
CREATE INDEX external_accounts_handle_idx ON app_private.external_accounts(handle_key);
CREATE TABLE app_private.codeforces_profile_cache(
 account_id uuid PRIMARY KEY REFERENCES app_private.external_accounts(id) ON DELETE CASCADE,
 handle text NOT NULL,
 rating integer, max_rating integer,
 rank text CHECK (rank IS NULL OR length(rank)<=80),
 registration_seconds bigint,
 fetched_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE app_private.codeforces_contest_cache(
 id integer PRIMARY KEY DEFAULT 1 CHECK(id=1),
 contests jsonb NOT NULL DEFAULT '[]'::jsonb CHECK(jsonb_typeof(contests)='array'),
 fetched_at timestamptz,
 next_refresh_at timestamptz,
 last_error text
);
CREATE TABLE app_private.codeforces_rate_slots(
 name text PRIMARY KEY,
 next_at timestamptz NOT NULL DEFAULT '-infinity'::timestamptz
);
INSERT INTO app_private.codeforces_rate_slots(name) VALUES('global') ON CONFLICT DO NOTHING;
CREATE TABLE app_private.codeforces_observations(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 account_id uuid NOT NULL REFERENCES app_private.external_accounts(id) ON DELETE CASCADE,
 upstream_submission_id bigint NOT NULL,
 verdict text CHECK(length(verdict)<=40),
 fetched_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(account_id,upstream_submission_id)
);
DO $$ DECLARE t record; BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='app_private'
 AND tablename IN ('external_accounts','codeforces_profile_cache',
 'codeforces_contest_cache','codeforces_rate_slots','codeforces_observations') LOOP
 EXECUTE format('ALTER TABLE app_private.%I ENABLE ROW LEVEL SECURITY',t.tablename);
 EXECUTE format('REVOKE ALL ON app_private.%I FROM PUBLIC, anon, authenticated',t.tablename);
 END LOOP;
END $$;
CREATE FUNCTION api.link_codeforces(handle text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE a app_private.external_accounts%ROWTYPE;
BEGIN
 IF NOT app_private.can_train() THEN
 RAISE EXCEPTION 'not_eligible' USING ERRCODE='42501'; END IF;
 IF handle IS NULL OR handle !~ '^[A-Za-z0-9_.-]{3,24}$' THEN
 RAISE EXCEPTION 'invalid_handle' USING ERRCODE='22023'; END IF;
 INSERT INTO app_private.external_accounts(owner_id,handle,handle_key)
 VALUES(auth.uid(),handle,lower(handle))
 ON CONFLICT(owner_id) DO UPDATE SET handle=excluded.handle,
  handle_key=excluded.handle_key,approval_status='pending_validation',
  approved_handle_key=NULL,approved_by=NULL,approved_at=NULL,opted_in=false,
  next_refresh_at=NULL,version=app_private.external_accounts.version+1
 RETURNING * INTO a;
 DELETE FROM app_private.codeforces_profile_cache WHERE account_id=a.id;
 RETURN jsonb_build_object('id',a.id,'version',a.version,
 'approval_status',a.approval_status,'handle',a.handle,'opted_in',a.opted_in);
END $$;
CREATE FUNCTION api.my_codeforces() RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
DECLARE result jsonb;
BEGIN
 IF NOT app_private.can_train() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 SELECT jsonb_build_object('id',a.id,'handle',a.handle,'approval_status',a.approval_status,
 'opted_in',a.opted_in,'version',a.version,
 'profile',CASE WHEN p.account_id IS NULL THEN NULL
 ELSE jsonb_build_object('rating',p.rating,'max_rating',p.max_rating,'rank',p.rank,
 'fetched_at',p.fetched_at) END)
 INTO result FROM app_private.external_accounts a LEFT JOIN app_private.codeforces_profile_cache p
 ON p.account_id=a.id WHERE a.owner_id=auth.uid();
 RETURN coalesce(result,'{"state":"not_connected"}'::jsonb);
END $$;
CREATE FUNCTION api.disconnect_codeforces() RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NOT app_private.can_train() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 DELETE FROM app_private.external_accounts WHERE owner_id=auth.uid();
 RETURN true;
END $$;
CREATE FUNCTION api.opt_codeforces_leaderboard(enabled boolean) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NOT app_private.can_train() OR enabled IS NULL THEN
 RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 UPDATE app_private.external_accounts SET opted_in=enabled,version=version+1
 WHERE owner_id=auth.uid();
 IF NOT FOUND THEN RAISE EXCEPTION 'no_linked_account' USING ERRCODE='22023'; END IF;
 RETURN true;
END $$;
CREATE FUNCTION api.admin_review_codeforces(account uuid, approved boolean) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE row0 app_private.external_accounts%ROWTYPE;
BEGIN
 IF NOT app_private.caller_is_admin() OR approved IS NULL THEN
 RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 SELECT * INTO row0 FROM app_private.external_accounts WHERE id=account FOR UPDATE;
 IF NOT FOUND OR row0.approval_status NOT IN('pending_approval','rejected','approved')
 OR NOT EXISTS(SELECT 1 FROM app.subject_memberships s JOIN app.profiles p
 ON p.user_id=s.user_id WHERE s.user_id=row0.owner_id AND s.subject_id='informatics'
 AND s.active AND p.active AND p.role='student')
 THEN RAISE EXCEPTION 'invalid_account' USING ERRCODE='42501'; END IF;
 UPDATE app_private.external_accounts SET
 approval_status=CASE WHEN approved THEN 'approved' ELSE 'rejected' END,
 approved_handle_key=CASE WHEN approved THEN row0.handle_key ELSE NULL END,
 approved_by=CASE WHEN approved THEN auth.uid() ELSE NULL END,
 approved_at=CASE WHEN approved THEN now() ELSE NULL END,
 version=version+1 WHERE id=account;
 INSERT INTO app_private.audit_events(actor_id,action,target_id)
 VALUES(auth.uid(),'codeforces.reviewed',account);
 RETURN true;
END $$;
CREATE FUNCTION api.codeforces_leaderboard(max_results integer DEFAULT 50) RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NOT app_private.caller_enabled() OR max_results NOT BETWEEN 1 AND 100 THEN
 RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 RETURN (SELECT coalesce(jsonb_agg(t.data ORDER BY t.rating DESC NULLS LAST,t.handle),'[]'::jsonb)
 FROM (SELECT jsonb_build_object('display_name',u.display_name,'handle',a.handle,
   'rating',c.rating,'max_rating',c.max_rating,'rank',c.rank,
   'fetched_at',c.fetched_at) data,c.rating,a.handle
 FROM app_private.external_accounts a
 JOIN app.profiles u ON u.user_id=a.owner_id
 JOIN app.subject_memberships s ON s.user_id=a.owner_id AND s.subject_id='informatics'
 JOIN app_private.codeforces_profile_cache c ON c.account_id=a.id
 WHERE u.active AND u.role='student' AND s.active AND a.opted_in
 AND a.approval_status='approved' AND a.approved_handle_key=a.handle_key
 ORDER BY c.rating DESC NULLS LAST,a.handle LIMIT max_results) t);
END $$;
CREATE FUNCTION api.codeforces_contests() RETURNS jsonb
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NOT app_private.caller_enabled() THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 RETURN (SELECT jsonb_build_object('contests',contests,'fetched_at',fetched_at,
 'next_refresh_at',next_refresh_at,'last_error',last_error)
 FROM app_private.codeforces_contest_cache WHERE id=1);
END $$;
-- Service role may only call these for verified Edge operations, NEVER browser JWTs.
CREATE FUNCTION app_private.reserve_codeforces_fetch() RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 UPDATE app_private.codeforces_rate_slots SET next_at=clock_timestamp()+interval '3 seconds'
 WHERE name='global' AND next_at<=clock_timestamp();
 RETURN FOUND;
END $$;
CREATE FUNCTION app_private.store_codeforces_profile(
 account uuid, expected_version integer, profile jsonb) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE a app_private.external_accounts%ROWTYPE; rating_val integer;max_val integer;
BEGIN
 IF jsonb_typeof(profile)<>'object' THEN RAISE EXCEPTION 'invalid_profile' USING ERRCODE='22023'; END IF;
 SELECT * INTO a FROM app_private.external_accounts WHERE id=account FOR UPDATE;
 IF NOT FOUND OR a.version<>expected_version OR
 lower(profile->>'handle')<>a.handle_key THEN RETURN false; END IF;
 rating_val=CASE WHEN (profile->>'rating') ~ '^[-]?[0-9]{1,7}$' THEN (profile->>'rating')::integer ELSE NULL END;
 max_val=CASE WHEN (profile->>'maxRating') ~ '^[-]?[0-9]{1,7}$' THEN (profile->>'maxRating')::integer ELSE NULL END;
 INSERT INTO app_private.codeforces_profile_cache(account_id,handle,rating,max_rating,rank,
 registration_seconds,fetched_at)
 VALUES(a.id,a.handle,rating_val,max_val,
 left(coalesce(profile->>'rank',''),80),
 CASE WHEN (profile->>'registrationTimeSeconds') ~ '^[0-9]{1,12}$'
 THEN (profile->>'registrationTimeSeconds')::bigint ELSE NULL END,now())
 ON CONFLICT(account_id) DO UPDATE SET handle=excluded.handle,rating=excluded.rating,
 max_rating=excluded.max_rating,rank=excluded.rank,
 registration_seconds=excluded.registration_seconds,fetched_at=excluded.fetched_at;
 UPDATE app_private.external_accounts SET approval_status=
 CASE WHEN approval_status='pending_validation' THEN 'pending_approval' ELSE approval_status END,
 next_refresh_at=now()+interval '6 hours',version=version+
 CASE WHEN approval_status='pending_validation' THEN 1 ELSE 0 END WHERE id=a.id;
 RETURN true;
END $$;
CREATE FUNCTION app_private.store_codeforces_contests(contest_list jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF jsonb_typeof(contest_list)<>'array' OR jsonb_array_length(contest_list)>200
 THEN RAISE EXCEPTION 'invalid_contests' USING ERRCODE='22023'; END IF;
 INSERT INTO app_private.codeforces_contest_cache(id,contests,fetched_at,next_refresh_at,last_error)
 VALUES(1,contest_list,now(),now()+interval '20 minutes',NULL)
 ON CONFLICT(id) DO UPDATE SET contests=excluded.contests,fetched_at=excluded.fetched_at,
 next_refresh_at=excluded.next_refresh_at,last_error=NULL;
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION api.link_codeforces(text),api.my_codeforces(),api.disconnect_codeforces(),
 api.opt_codeforces_leaderboard(boolean),api.admin_review_codeforces(uuid,boolean),
 api.codeforces_leaderboard(integer),api.codeforces_contests()
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.link_codeforces(text),api.my_codeforces(),api.disconnect_codeforces(),
 api.opt_codeforces_leaderboard(boolean),api.admin_review_codeforces(uuid,boolean),
 api.codeforces_leaderboard(integer),api.codeforces_contests() TO authenticated;
REVOKE ALL ON FUNCTION app_private.reserve_codeforces_fetch(),
 app_private.store_codeforces_profile(uuid,integer,jsonb),
 app_private.store_codeforces_contests(jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION app_private.reserve_codeforces_fetch(),
 app_private.store_codeforces_profile(uuid,integer,jsonb),
 app_private.store_codeforces_contests(jsonb) TO service_role;
COMMIT;
