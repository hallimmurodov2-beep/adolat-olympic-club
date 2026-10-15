-- M3-M5 executable, transaction-rolled-back RLS/RPC integration.
-- Tests actual PostgreSQL role calls with signed claim contexts, not browser mocks.
BEGIN;
SELECT plan(15);
INSERT INTO auth.users(id,instance_id,aud,role,email,encrypted_password,email_confirmed_at,created_at,updated_at) VALUES
('31111111-1111-4111-8111-111111111111','00000000-0000-0000-0000-000000000000','authenticated','authenticated','m35-teacher@example.invalid','',now(),now(),now()),
('32222222-2222-4222-8222-222222222222','00000000-0000-0000-0000-000000000000','authenticated','authenticated','m35-student-a@example.invalid','',now(),now(),now()),
('33333333-3333-4333-8333-333333333333','00000000-0000-0000-0000-000000000000','authenticated','authenticated','m35-student-b@example.invalid','',now(),now(),now());
INSERT INTO app.profiles(user_id,email,display_name,role,active) VALUES
('31111111-1111-4111-8111-111111111111','m35-teacher@example.invalid','Teacher','teacher',true),
('32222222-2222-4222-8222-222222222222','m35-student-a@example.invalid','Student A','student',true),
('33333333-3333-4333-8333-333333333333','m35-student-b@example.invalid','Student B','student',true);
INSERT INTO app.subject_memberships(subject_id,user_id,active) VALUES
('informatics','32222222-2222-4222-8222-222222222222',true),
('informatics','33333333-3333-4333-8333-333333333333',true);
INSERT INTO app.classrooms(id,subject_id,teacher_id,name) VALUES
('34444444-4444-4444-8444-444444444444','math','31111111-1111-4111-8111-111111111111','{"en":"Math"}'::jsonb);
INSERT INTO app.classroom_memberships(classroom_id,student_id) VALUES
('34444444-4444-4444-8444-444444444444','32222222-2222-4222-8222-222222222222');
INSERT INTO app.problems(id,classroom_id,title,statement,published)
 VALUES('35555555-5555-4555-8555-555555555555','34444444-4444-4444-8444-444444444444',
 '{"en":"Example"}','{"en":"Answer this"}',true);
INSERT INTO app_private.problem_secrets(problem_id,solution) VALUES
 ('35555555-5555-4555-8555-555555555555','{"en":"SECRET"}');
INSERT INTO app.training_cycles(id,owner_id,title) VALUES
 ('36666666-6666-4666-8666-666666666666','32222222-2222-4222-8222-222222222222','{"en":"Train"}'),
 ('37777777-7777-4777-8777-777777777777','33333333-3333-4333-8333-333333333333','{"en":"Train B"}');
INSERT INTO app.training_circles(id,subject_id,created_by,name)
VALUES('38888888-8888-4888-8888-888888888888','informatics',
'32222222-2222-4222-8222-222222222222','{"en":"Math code"}');
INSERT INTO app.circle_members(circle_id,user_id,role,status) VALUES
('38888888-8888-4888-8888-888888888888','32222222-2222-4222-8222-222222222222','facilitator','active');

SELECT set_config('request.jwt.claims',
'{"sub":"31111111-1111-4111-8111-111111111111","session_id":"teacher-session-12345","role":"authenticated"}',true);
SET LOCAL ROLE authenticated;
SELECT is(api.bootstrap()->'user'->>'role','teacher','Teacher bootstrap from DB');
SELECT is(jsonb_array_length(api.list_classroom_problems('34444444-4444-4444-8444-444444444444')),1,'Teacher can list own problem');
SELECT ok(api.create_problem('34444444-4444-4444-8444-444444444444','{"en":"New"}','{"en":"Body"}') IS NOT NULL,'Teacher creates problem');
RESET ROLE;

SELECT set_config('request.jwt.claims',
'{"sub":"32222222-2222-4222-8222-222222222222","session_id":"a-session-12345678","role":"authenticated"}',true);
SET LOCAL ROLE authenticated;
SELECT is(api.bootstrap()->>'can_train','true','Eligible student bootstraps Informatics');
SELECT is(jsonb_array_length(api.list_classroom_problems('34444444-4444-4444-8444-444444444444')),1,'Student sees published only');
SELECT is((api.save_personal_plan('36666666-6666-4666-8666-666666666666','My goal','','','{}',0)->>'version')::integer,1,'Student creates own private plan');
SELECT ok(api.add_training_item((SELECT id FROM app.training_plans
 WHERE cycle_id='36666666-6666-4666-8666-666666666666'),
 '39999999-9999-4999-8999-999999999999','Practice') IS NOT NULL,'Can add private training item');
SELECT throws_ok($SELECT api.leave_training_circle('38888888-8888-4888-8888-888888888888')$,
'23514','last_facilitator','Last facilitator cannot abandon circle');
RESET ROLE;
SELECT ok(NOT has_table_privilege('authenticated','app_private.problem_secrets','SELECT'),'No solution grant');
SELECT ok(NOT has_table_privilege('authenticated','app_private.grades','SELECT'),'No grade grant');
SELECT ok(NOT has_table_privilege('authenticated','app.training_items','INSERT'),'No direct training writes');

SELECT set_config('request.jwt.claims',
'{"sub":"33333333-3333-4333-8333-333333333333","session_id":"b-session-12345678","role":"authenticated"}',true);
SET LOCAL ROLE authenticated;
SELECT is((SELECT count(*)::integer FROM api.my_training_plans),0,'Student B cannot read A private plan');
SELECT is(api.request_circle_join('38888888-8888-4888-8888-888888888888'),'pending','Circle joining requires facilitator approval');
RESET ROLE;
UPDATE app.profiles SET active=false WHERE user_id='33333333-3333-4333-8333-333333333333';
SET LOCAL ROLE authenticated;
SELECT throws_ok($$SELECT api.bootstrap()$$,'42501','unauthenticated','Disabled user denied');
RESET ROLE;
SELECT * FROM finish();
ROLLBACK;
