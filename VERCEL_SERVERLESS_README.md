# Vercel serverless compatibility branch (OPTIONAL, not the Cloudflare migration)

This branch packages the existing, implemented **FastAPI + native TypeScript** Adolat Olympic Club app for Vercel's on-demand Python runtime. It retains the Supabase PostgreSQL and private Storage integration, the original UI, every existing API route, and the old backend-mediated security model.

**It does not eliminate FastAPI source code.** It removes the dependency on an *always-running Render instance*. This is a separate candidate, not the Phase 2 Cloudflare/Supabase-native rewrite.

## Test evidence

In the coding environment, all 147 selected non-browser Python regression tests passed (security, workflows, Codeforces, Storage, recovery, Informatics and i18n), along with `tsc --noEmit`, Python import and package structure checks. Actual Vercel hosted deployment has NOT been performed or verified.

## Deployment TOGETHER later (don't cut over now)

1. Check Vercel's terms. Hobby use is limited to personal, non-commercial use; a school club may need a different plan.
2. Import this branch in a NEW Vercel staging project or run `vercel` from the extracted ZIP.
3. Set protected server-side environment variables: `APP_ENV=production`, `APP_ORIGIN=https://<preview-alias>`, `APP_SECRET` (32+ random characters), `DATABASE_URL` (Supabase session pooler), `STORAGE_BACKEND=supabase`, `SUPABASE_URL`, `SUPABASE_STORAGE_BUCKET`, `SUPABASE_STORAGE_SERVER_KEY`, plus flags from `.env.production.example`. Never place those secrets in client code. Preview and production aliases must match configured origin.
4. Vercel detects root `app.py`, which exports `server.app:app`. The `public` directory serves the existing HTML, CSS, scripts, logos and locales as static CDN assets; the Python function serves `/api`.
5. Verify `/api/health`, `/api/ready`, all roles/invitations, full teaching journeys, Informatics/circles, private files, Codeforces and idle/reconnect. Pay particular attention to serverless SSE duration and 8MiB uploads.
6. Verify backups, secrets, user-role isolation, performance from Dushanbe, and provider terms before approving production. Render and the existing Supabase setup remain UNCHANGED until explicit authorization.

**Release status: locally verified deployment candidate, pending hosted acceptance.** 
