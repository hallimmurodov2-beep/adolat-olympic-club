-- M7: minimal private change notifications, no hidden scores/content/notes.
BEGIN;
CREATE TABLE app.events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 recipient_id uuid NOT NULL REFERENCES app.profiles(user_id) ON DELETE CASCADE,
 kind text NOT NULL CHECK(kind ~ '^[a-z_]{3,40}$'),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX events_recipient_cursor_idx ON app.events(recipient_id,id);
CREATE TABLE app.notifications (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 recipient_id uuid NOT NULL REFERENCES app.profiles(user_id) ON DELETE CASCADE,
 kind text NOT NULL CHECK(kind ~ '^[a-z_]{3,40}$'),
 title jsonb NOT NULL DEFAULT '{}'::jsonb,
 href text NOT NULL DEFAULT '' CHECK(length(href)<=250),
 acknowledged_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX notifications_recipient_time_idx ON app.notifications(recipient_id,created_at DESC);
ALTER TABLE app.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE app.notifications ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON app.events,app.notifications FROM PUBLIC,anon,authenticated;
GRANT SELECT ON app.events,app.notifications TO authenticated;
CREATE POLICY owner_event_select ON app.events FOR SELECT TO authenticated
 USING(recipient_id=(SELECT auth.uid()) AND (SELECT app_private.caller_enabled()));
CREATE POLICY owner_notification_select ON app.notifications FOR SELECT TO authenticated
 USING(recipient_id=(SELECT auth.uid()) AND (SELECT app_private.caller_enabled()));
CREATE FUNCTION api.events_since(last_id bigint DEFAULT 0, limit_count integer DEFAULT 60)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NOT app_private.caller_enabled() OR last_id<0 OR limit_count NOT BETWEEN 1 AND 100
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 RETURN (SELECT jsonb_build_object('events',coalesce(jsonb_agg(jsonb_build_object(
 'id',e.id,'kind',e.kind,'created_at',e.created_at) ORDER BY e.id),'[]'::jsonb),
 'server_now',(extract(epoch FROM clock_timestamp())*1000)::bigint)
 FROM (SELECT id,kind,created_at FROM app.events WHERE recipient_id=auth.uid()
 AND id>last_id ORDER BY id LIMIT limit_count) e);
END $$;
CREATE FUNCTION api.my_notifications(limit_count integer DEFAULT 40)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path='' AS $$
BEGIN
 IF NOT app_private.caller_enabled() OR limit_count NOT BETWEEN 1 AND 100
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 RETURN (SELECT coalesce(jsonb_agg(jsonb_build_object('id',n.id,'kind',n.kind,
 'title',n.title,'href',n.href,'read',n.acknowledged_at IS NOT NULL,
 'created_at',n.created_at) ORDER BY n.created_at DESC),'[]'::jsonb)
 FROM (SELECT * FROM app.notifications WHERE recipient_id=auth.uid()
 ORDER BY created_at DESC LIMIT limit_count)n);
END $$;
CREATE FUNCTION api.mark_notifications_read(ids uuid[]) RETURNS integer
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE n integer;
BEGIN
 IF NOT app_private.caller_enabled() OR ids IS NULL OR cardinality(ids)>100
 THEN RAISE EXCEPTION 'forbidden' USING ERRCODE='42501'; END IF;
 UPDATE app.notifications SET acknowledged_at=now()
 WHERE recipient_id=auth.uid() AND id=ANY(ids) AND acknowledged_at IS NULL;
 GET DIAGNOSTICS n=ROW_COUNT;RETURN n;
END $$;
CREATE FUNCTION app_private.owner_training_event() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 -- Trigger is installed exclusively on tables that have an owner_id.
 INSERT INTO app.events(recipient_id,kind)
 VALUES(NEW.owner_id,'training_changed');
 RETURN NEW;
END $$;
CREATE TRIGGER plan_invalidate AFTER INSERT OR UPDATE ON app.training_plans
 FOR EACH ROW EXECUTE FUNCTION app_private.owner_training_event();
CREATE TRIGGER item_invalidate AFTER INSERT OR UPDATE ON app.training_items
 FOR EACH ROW EXECUTE FUNCTION app_private.owner_training_event();
CREATE TRIGGER practice_invalidate AFTER INSERT ON app.practice_entries
 FOR EACH ROW EXECUTE FUNCTION app_private.owner_training_event();
DO $$BEGIN
 IF EXISTS(SELECT 1 FROM pg_publication WHERE pubname='supabase_realtime')
 AND NOT EXISTS(SELECT 1 FROM pg_publication_tables WHERE pubname='supabase_realtime'
 AND schemaname='app' AND tablename='events') THEN
 ALTER PUBLICATION supabase_realtime ADD TABLE app.events;
 END IF;
END $$;
-- The realtime channel may emit the (id,kind,recipient_id) only. Never include
-- full notes/grade bodies in events. RLS must authorize current recipient.
REVOKE ALL ON FUNCTION api.events_since(bigint,integer),
 api.my_notifications(integer),api.mark_notifications_read(uuid[]) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION api.events_since(bigint,integer),
 api.my_notifications(integer),api.mark_notifications_read(uuid[]) TO authenticated;
COMMIT;
