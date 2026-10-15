# M1/M2 staging handoff

## Implemented locally and checked
Run `npm ci --ignore-scripts && npm run typecheck && npm run build:cloudflare`; publish directory `dist`. Original HTML, stylesheet, compiled TS modules, logos, vendor assets and both locale JSON files are copied with no credentials. Only `/api/session/*` invokes future Pages Functions; no broker exists until M3. The login UI is not a working login on static hosting yet. Current CSP is same-origin only until the M3 Supabase adapter is reviewed. Vite is intentionally deferred until M3; a native TypeScript shell needs no bundler dependency today.

## M1 hosted blocker
Create a **new** Cloudflare Pages project and a **new** Supabase project. Connect only the migration branch, not `main`. Never reuse the old project reference, old role password or Storage credentials. The generated `dist` is not itself a live deployment. Verify the Russian and English sign-in UI and brand assets at a Pages preview; data API functionality requires M3.

## M2 hosted blocker
Only with explicit operator selection of the new disposable Supabase project, run `supabase start`, `supabase db reset`, then `supabase test db` locally. Set Data API custom exposed schemas to only `api`; `app` and `app_private` must remain unexposed. Test real JWT direct REST/RPC access from anonymous, two students, disabled accounts, teacher and admin. No newly defined high-risk domain writes are enabled by M2. Document test outcomes before marking M2 complete.

## Unconditional safeguards
Do NOT use the legacy `olympiados_app` role or run `supabase/apply_policies.sql` for the new project. Never place `sb_secret_*` or cookie keys in compiled assets or committed build variables. Supabase Auth, account provisioning, Pages session broker, SMTP, private file acceptance and the full app API adapter are M3–M6 tasks, not M2 accomplishments.
