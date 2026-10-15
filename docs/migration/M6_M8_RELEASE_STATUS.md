# Serverless migration — M6–M8 release status and deployment-together checklist

**Status: NOT READY TO LAUNCH.** This document is a truthful technical handoff, not an M8 completion certificate.

## Current proposed infrastructure
- Cloudflare Pages static site, original native TypeScript/CSS and RU/EN branding.
- A separate **new** Supabase project: Auth, PostgreSQL (only custom Data API schema `api`), RLS, private Storage and small Edge Functions.
- No continuous Python server. Legacy Render remains operational and **must not be removed during staging**.

## Implementation presently in this branch
- M6: Codeforces account linking, explicit opt-in, admin approval, profile and contest caches, durable shared throttle, official API Edge prototype. Official Codeforces production connectivity is **not tested**.
- M6: Private quarantine and accepted-file buckets; reservation and quota SQL; upload validation/normalization Edge prototype; per-request authenticated file-delivery gateway. These are intentionally feature-flagged OFF pending hosted security tests. ImageMagick WASM may exceed Supabase Edge CPU/memory at the full 8-MiB input cap. Failed normalization is rejected, not trusted.
- M7: Private change-event RLS, minimal Realtime publication, polling and foreground recovery module, bounded scheduled cleanup (separate machine secret).
- M8: CI and hosted smoke preparation; no cutover.

## Critical blockers inherited from M3–M5
1. The existing `frontend/api.ts` still routes 113 legacy endpoint contracts to FastAPI. The new native TypeScript transport module is not wired into existing UI; the Cloudflare build **cannot operate as the original school app**. All old screens and their data adapters must be connected and regression-tested.
2. Incomplete M3 Auth: browser invitation acceptance, password recovery, cross-tab token refresh, custom SMTP, automated native browser login/role tests.
3. Incomplete M4: group submissions, immutable assessment snapshots for all activity modes, complete grading/review/hints/drafts, announcements, problem sets and full competition timers.
4. Incomplete M5: facilitator transfers, carry-forward, moderation reports/resolution, complete peer discussion restrictions and all workflow pages.
5. Hosted Supabase and Cloudflare staging projects are not connected. Real Auth JWT, Data API, Storage, and browser acceptance tests haven't been executed against live services.
6. No independent encrypted PostgreSQL-plus-private-object restoration demonstration or complete recovery runbook for a launched school.
7. Supabase Free inactivity pausing must be tested and treated separately from Cloudflare's always-served static assets.

## Deployment-together, only AFTER blockers close
1. Create **brand-new** Supabase staging project, disallow public signup, configure `api` as the **only custom exposed Data API schema**; `app` and `app_private` must not be exposed.
2. Apply migrations from scratch to isolated staging only. Require `supabase db reset && supabase test db` locally first.
3. Configure `adolat-quarantine` and `adolat-files` private buckets. Confirm no browser LIST/SELECT/UPDATE/DELETE/signed link ability on accepted files. Test actual Storage API operations with JWT.
4. Configure Cloudflare Pages preview on migration branch; public vars only are Supabase origin and publishable key. **Never publish service-role secrets in VITE variables or JS.**
5. Put secret Edge credentials in Supabase secrets; keep `BROKER_ENABLED`, `ACCOUNT_ADMIN_ENABLED`, `CODEFORCES_SYNC_ENABLED`, `UPLOAD_PROCESS_ENABLED`, `FILE_DELIVERY_ENABLED` and `MAINTENANCE_ENABLED` OFF until each module passes acceptance.
6. Configure verified school-controlled SMTP, email callback origins and a secure initial administrator bootstrap; invitation scope must be tested with two student identities.
7. Run `node scripts/verify-staging.mjs` with synthetic two-student credentials in a private terminal; verify expected privacy denial directly through REST/RPC. This script is a small smoke only, **not a full acceptance certificate**.
8. Run actual hosted browser journeys for administrator/teacher/students in English and Russian, all original features, and Storage/Codeforces/Realtime outages/reconnects. Verify no secrets in built assets or logs.
9. Verify encrypted DB+object backup/restore in a separate project; measure Dushanbe network latency after inactivity. Do not claim Supabase Free eliminates idle pausing.
10. **Only after owner approval**, create separately configured production Supabase and Cloudflare projects and execute controlled cutover. Never delete Render/legacy Supabase or existing users as part of the migration.

## Automated checks are necessary but insufficient
Dedicated GitHub Actions migration CI runs local Supabase DB reset, pgTAP and static build. CI does NOT assert actual Vercel/Cloudflare hosting, hosted Storage path behavior, edge CPU limits, login callbacks, email delivery, or full feature parity. If tests are queued or red, report them honestly.

## Required release sign-off
Security — no exposure to private training, hidden grades, files or roles via direct REST/RPC/Realtime/Storage.
Functionality — every currently implemented V1/V2 student, teacher and administrator workflow passes.
Reliability — cold page, auth refresh, after-idle tab navigation and connectivity-recovery budgets measured.
Recovery — real DB and Storage recovery rehearsed.
After those gates pass, and not before, call the replacement complete.
