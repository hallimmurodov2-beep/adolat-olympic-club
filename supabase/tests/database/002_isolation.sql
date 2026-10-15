-- Real caller-scoped SQL isolation with synthetic, transactional Auth identities.
BEGIN;
SELECT plan(8);
INSERT INTO auth.users(id,instance_id,aud,role,email,encrypted_password,email_confirmed_at,created_at,updated_at) VALUES
 ('11111111-1111-4111-8111-111111111111','00000000-0000-0000-0000-000000000000','authenticated','authenticated','m2-a@example.invalid','',now(),now(),now()),
 ('22222222-2222-4222-8222-222222222222','00000000-0000-0000-0000-000000000000','authenticated','authenticated','m2-b@example.invalid','',now(),now(),now());
INSERT INTO app.profiles(user_id,email,display_name,role,active) VALUES
 ('11111111-1111-4111-8111-111111111111','m2-a@example.invalid','Student A','student',true),
 ('22222222-2222-4222-8222-222222222222','m2-b@example.invalid','Student B','student',true);
INSERT INTO app.training_cycles(id,owner_id) VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','11111111-1111-4111-8111-111111111111'),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','22222222-2222-4222-8222-222222222222');
INSERT INTO app.training_plans(id,cycle_id,owner_id,goal) VALUES
 ('cccccccc-cccc-4ccc-8ccc-cccccccccccc','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','11111111-1111-4111-8111-111111111111','A private goal'),
 ('dddddddd-dddd-4ddd-8ddd-dddddddddddd','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','22222222-2222-4222-8222-222222222222','B private goal');
SELECT set_config('request.jwt.claims','{"sub":"11111111-1111-4111-8111-111111111111","session_id":"session-aaaaaaaaaaaa","role":"authenticated"}',true);
SET LOCAL ROLE authenticated;
SELECT is((SELECT count(*)::integer FROM api.my_training_plans),1,'A sees only one plan');
SELECT is((SELECT count(*)::integer FROM api.my_training_plans WHERE goal='B private goal'),0,'A cannot see B plan');
SELECT is((SELECT count(*)::integer FROM api.my_profile),1,'A sees own profile');
SELECT is((SELECT count(*)::integer FROM api.my_profile WHERE role='admin'),0,'A cannot impersonate admin');
RESET ROLE;
SELECT set_config('request.jwt.claims','{"sub":"22222222-2222-4222-8222-222222222222","session_id":"session-bbbbbbbbbbbb","role":"authenticated"}',true);
SET LOCAL ROLE authenticated;
SELECT is((SELECT count(*)::integer FROM api.my_training_plans),1,'B sees only one plan');
RESET ROLE;
UPDATE app.profiles SET active=false WHERE user_id='22222222-2222-4222-8222-222222222222';
SET LOCAL ROLE authenticated;
SELECT is((SELECT count(*)::integer FROM api.my_training_plans),0,'Inactive B denied despite JWT');
RESET ROLE;
INSERT INTO app_private.revoked_sessions(session_id,user_id,reason)
 VALUES('session-aaaaaaaaaaaa','11111111-1111-4111-8111-111111111111','admin');
SELECT set_config('request.jwt.claims','{"sub":"11111111-1111-4111-8111-111111111111","session_id":"session-aaaaaaaaaaaa","role":"authenticated"}',true);
SET LOCAL ROLE authenticated;
SELECT is((SELECT count(*)::integer FROM api.my_training_plans),0,'Revoked A denied despite JWT');
SELECT is((SELECT count(*)::integer FROM api.my_profile),0,'Revoked A profile denied');
RESET ROLE;
SELECT * FROM finish();
ROLLBACK;
