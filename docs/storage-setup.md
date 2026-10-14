# Private Supabase Storage — checkpoint runbook

**No bucket, server key or live upload was provisioned/tested here.** The adapter and durable upload flow have deterministic local/mock tests. Complete the real verification below before a pilot. Existing-school-object migration and verified encrypted object backups remain Phase 4 work.

## Bucket and secrets

Using the authorized school's project dashboard, create **private** bucket `olympiados-attachments`. Disable public access. Set a maximum object size of 8 MiB and allow only the app's supported normalized image/document/text content types (PNG/JPEG, PDF, UTF-8 text and the retained source-text types). The application's byte/type validation is still required and may be stricter than the bucket. Do not grant browser `anon` or `authenticated` upload/read/list access to this bucket. No separate browser Supabase client is used.

Supply only to the backend:

```text
STORAGE_BACKEND=supabase
SUPABASE_URL=https://<your-actual-project>.supabase.co
SUPABASE_STORAGE_BUCKET=olympiados-attachments
SUPABASE_STORAGE_SERVER_KEY=<server-only-key>
```

The implementation sends an opaque `sb_secret_...` key in the `apikey` header, not as an invalid JWT bearer. For a legacy service-role JWT it sends the documented server API key plus bearer header. Only choose a key mechanism verified on the target project. The server key can bypass Storage policies: anyone with it is privileged, so never expose it to the browser, public CI, URLs/logs or screenshots. Store it in the approved secret store and plan rotation.

## Application gateway and retry contract

All user bytes flow through `/api/files/{id}` after normal FastAPI authorization. There are no public/signed per-student URLs. Object keys are opaque `files/<uuid>`, with no names, email, grade or solution in the key. HTTP reads stream under private/no-store, nosniff and sandbox/content-disposition rules; the upstream stream is closed on cancellation. No HTML/SVG/program execution is enabled.

Uploads first reserve target slots and global/user bytes, commit that short reservation, then validate/put/stat outside the DB transaction, recheck current session/membership/time access, and finalize a hashed ready file. Exact retries use the same client UUID and normalized payload; a differing retry is rejected. A lost remote response is reconciled rather than causing an unconditional overwrite. Failed cleanup remains accounted as reserved bytes until absence is confirmed. Immutable submission references prevent deletion.

Default application budgets: 8 MiB per input/stored object, 12 per target, 32 MiB/student, 128 MiB/staff, 500 MiB global warning and 700 MiB hard cap. They can be configured lower, and **must be reconciled against real migrated usage** before any production import. These are application choices, not a claim about today's provider allowance. `GET /api/files/quota` shows the current user's budget; broad operator dashboards remain unfinished.

`python -m server.cli reconcile-uploads` processes a bounded set of expired intents (initial 24-hour grace) and never deletes a committed referenced file. It is an explicit operator action, not a promised always-running background worker. Record its results and schedule according to an approved school process. Legacy `cleanup` is not a cloud object backup or complete lifecycle tool.

The UI offers a preview and explicit JPEG option for a photo. PNG remains the default and is retained for transparency. It does not secretly resize archived work. After a network failure, keep the page open and use Retry so the same File/key is reused. Browser File objects are not restored after a full page reload; the UI does not claim otherwise.

## Required live staging verification

Use only synthetic files/accounts. Verify anonymous direct bucket reads fail; unrelated/removed accounts and unreleased group-file IDs fail through the app; authorized teacher and immutable-submission access succeeds; PNG/JPEG/PDF/text bytes and checksums match; no download is public-cacheable. Exercise exact upload retry, failed remote response, quota contention, account disable/membership removal during upload, cancelled stream, app restart, failed delete and reconciliation.

Verify that accepted files survive process redeploy, and that metadata cannot be accepted when the object is missing or inaccessible. Inspect secrets only in backend configuration, never frontend assets. Test source and destination sizes/headers on the actual storage service. A local/mock test is not evidence of any of these provider properties.

Finally complete a database **and object bytes** encrypted backup/restore to an isolated target with an approved custodian. A DB-only backup is insufficient; the full F05 tool is still pending and is a rollout blocker.

Primary sources checked during implementation: https://supabase.com/docs/guides/api/api-keys ; https://supabase.com/docs/guides/storage/security/access-control ; https://supabase.com/docs/guides/storage/buckets/fundamentals ; https://supabase.com/docs/guides/platform/backups . No live key or bucket behavior is asserted from documentation alone.
