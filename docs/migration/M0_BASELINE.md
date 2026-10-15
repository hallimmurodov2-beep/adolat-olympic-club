# M0 — baseline frozen for serverless migration

- Source: `hallimmurodov2-beep/adolat-olympic-club` main at `956c4496dc7fa0f50501d6fa90b9287bdab9ef03`.
- Source tree SHA: `901bbcee41c9bc6d2338a4cbc0d2abdd6432f167`.
- Migration branch: `migration/cloudflare-supabase-m0-m2`.
- The existing Render deployment and Supabase project containing the `olympiados` schema remain **untouched**; no old records are imported.
- Baseline: 11 FastAPI router modules / 113 route-method declarations; 49 model tables (33 original, 16 V2). These are inventoried in the Phase 1/2 audits.
- Frontend: native TypeScript compiled by `tsc`, `static/index.html`, MathJax, Prism, logos, original CSS, hash routing, Russian/English.
- Functional parity catalog: invitation-only admin/teacher/student auth; classrooms, memberships, problems, activities, deadlines, group work, drafts, submissions, grading and embargoes; private Informatics training, circles/moderation, Codeforces; files/quota, notifications, audits, real-time, recovery.
- Current legacy CI is **not** a certified green production release gate. Live PostgreSQL concurrency, hosted Storage, backup restore, Codeforces reachability and exhaustive browser checks still need explicit verification.
- Never apply this branch's new migrations to the old Supabase database. New project with separate credentials only, confirmed by an operator.
- Never run legacy `supabase/bootstrap.sql` or `supabase/apply_policies.sql` in the new project.
- No Render deployment, old database edit, user invitation, cutover, or resource deletion is authorized by these M0–M2 commits.
- M1 means static packaging only; M3 delivers working authentication. M2 focuses security foundations and default-deny SQL. M4/M5 extend domain tables and transactional functionality.
- Acceptance gates: real JWT direct REST/RPC security checks, Supabase-hosted Storage checks, PostgreSQL concurrency, real browser roles, verified DB+object restoration and measured after-idle navigation.
