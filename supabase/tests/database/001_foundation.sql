-- pgTAP structural and explicit negative-grant tests for the M2 foundation.
-- End-to-end RLS/Storage testing under real Supabase JWTs remains a separate exit gate.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(20);
SELECT has_schema('api','Browser API schema exists');
SELECT has_schema('app','Unexposed app schema exists');
SELECT has_schema('app_private','Unexposed confidential schema exists');
SELECT has_table('app','profiles','Profiles table exists');
SELECT has_table('app','training_plans','Private plans table exists');
SELECT has_table('app_private','problem_secrets','Solutions are separate');
SELECT has_table('app_private','grades','Hidden grades are separate');
SELECT has_view('api','my_profile','Profile view exists');
SELECT has_view('api','my_training_plans','Training view exists');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='app.profiles'::regclass),'Profile RLS enabled');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='app.training_plans'::regclass),'Training plan RLS enabled');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='app.classrooms'::regclass),'Classroom RLS enabled');
SELECT ok((SELECT relrowsecurity FROM pg_class WHERE oid='app_private.problem_secrets'::regclass),'Solution RLS enabled');
SELECT ok(NOT has_table_privilege('anon','app.profiles','SELECT'),'Anon cannot read profiles');
SELECT ok(NOT has_table_privilege('authenticated','app.profiles','UPDATE'),'User cannot self-promote via UPDATE');
SELECT ok(NOT has_table_privilege('authenticated','app_private.problem_secrets','SELECT'),'No secret SELECT');
SELECT ok(NOT has_table_privilege('authenticated','app_private.grades','SELECT'),'No hidden grading SELECT');
SELECT ok(NOT has_table_privilege('authenticated','app.training_plans','INSERT'),'No training plan writes before M5');
SELECT ok(NOT has_table_privilege('authenticated','app.classroom_memberships','DELETE'),'No direct member offboarding');
SELECT ok(NOT has_function_privilege('anon','app_private.caller_enabled()','EXECUTE'),'No anonymous role helper call');
SELECT * FROM finish();
ROLLBACK;
