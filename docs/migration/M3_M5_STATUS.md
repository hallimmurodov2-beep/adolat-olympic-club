# Phase 4 M3–M5 implementation checkpoint

Branch: migration/cloudflare-supabase-m3-m5 (based on M0–M2 branch). No production cutover.

## Implemented
- M3: Cloudflare Pages session login, session lookup and logout handler. Uses same-origin POST Origin validation, secure HttpOnly SameSite cookies, server-side Supabase URL and publishable/anon key, and an active-profile check. Logout calls a per-session revocation RPC. No privileged service-role key in the client.
- M4: security-definer RPCs for idempotent student submissions and teacher/admin grading, with membership checks and separated grade storage.
- M5: private owner-only training-plan upsert and Informatics discoverable-circle pending join RPC.

## Not implemented / release blockers
- The existing frontend still calls legacy /api routes: these new endpoints are NOT a working replacement for the legacy app. M3 needs invitation issuance/acceptance, registration and password reset, robust refresh rotation and account deactivation handling; browser API adapter, CSRF token integration and full parity remain incomplete.
- M4 needs activity/problem authoring, snapshotting, enrollment, grade release and comprehensive regression tests.
- M5 needs cycle/circle creation, approvals, facilitator management, planning UI and tests.
- The cookie access token expires after 15 minutes; refresh cookie is reserved but no refresh handler yet. The logout revocation call currently clears browser cookies even when upstream revocation fails; production must fail closed/retry revocation and verify logout on all devices.
- The static builder currently only routes /api/session/* to Functions. Hosted project provisioning, live Supabase migration, Auth config, integration tests and security tests are NOT verified.
- M6–M8 are NOT approved for cutover. Old Render and old Supabase remain untouched.
