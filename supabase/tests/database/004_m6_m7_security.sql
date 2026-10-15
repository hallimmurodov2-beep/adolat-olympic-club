-- M6 and M7 negative grant + user authorization tests on isolated Supabase DB.
BEGIN;
SELECT plan(15);
SELECT has_table('app_private','external_accounts','Account links stay private');
SELECT has_table('app_private','upload_intents','Upload reservations exist');
SELECT has_table('app','stored_files','Accepted file records exist');
SELECT has_table('app','events','Private invalidation events exist');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='app.stored_files'::regclass),'Files enforce RLS');
SELECT ok(NOT has_table_privilege('authenticated','app.stored_files','SELECT'),'No direct accepted-file SELECT');
SELECT ok(NOT has_table_privilege('authenticated','app_private.external_accounts','SELECT'),'Private linked accounts inaccessible');
SELECT ok(NOT has_function_privilege('authenticated','api.edge_file_location(uuid)','EXECUTE'),'Object paths service only');
SELECT ok(NOT has_function_privilege('authenticated','api.edge_store_codeforces_profile(uuid,integer,jsonb)','EXECUTE'),'Profiles not forgeable');
SELECT ok((SELECT NOT public FROM storage.buckets WHERE id='adolat-files'),'Accepted bucket private');
SELECT ok((SELECT NOT public FROM storage.buckets WHERE id='adolat-quarantine'),'Quarantine private');
INSERT INTO auth.users(id,instance_id,aud,role,email,encrypted_password,email_confirmed_at,created_at,updated_at)
 VALUES ('41111111-1111-4111-8111-111111111111','00000000-0000-0000-0000-000000000000',
 'authenticated','authenticated','m67-student@example.invalid','',now(),now(),now());
INSERT INTO app.profiles(user_id,email,display_name,role,active)
 VALUES('41111111-1111-4111-8111-111111111111','m67-student@example.invalid','Student M6','student',true);
INSERT INTO app.subject_memberships(subject_id,user_id,active)
 VALUES('informatics','41111111-1111-4111-8111-111111111111',true);
SELECT set_config('request.jwt.claims',
'{"sub":"41111111-1111-4111-8111-111111111111","session_id":"m67-session-aaaaaaaa","role":"authenticated"}',true);
SET LOCAL ROLE authenticated;
SELECT is(api.link_codeforces('Student_A')->>'approval_status','pending_validation','Handle pending official validation');
SELECT is(api.my_codeforces()->>'handle','Student_A','Self-only handle projection');
SELECT is(api.codeforces_leaderboard(10)::text,'[]','No unapproved leaderboard entry');
SELECT is(api.my_notifications(10)::text,'[]','No notifications by default');
RESET ROLE;
SELECT * FROM finish();
ROLLBACK;
