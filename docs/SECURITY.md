# Security and privacy — implementation boundaries

**This is not an independent security audit, production certification or legal-compliance determination.** Automated synthetic tests support specified cases only. See [RELEASE-GATES.md](RELEASE-GATES.md).

## Retained account and teaching controls

V1 Argon2id passwords, hashed opaque session tokens, HttpOnly/SameSite cookies, production Secure cookies, session revocation, invitation registration, CSRF/origin checks and contextual classroom/assessment permissions remain. Student source text is never executed. Teacher grading and published snapshots retain their existing semantics. Authentication/image hashing now shares bounded CPU admission; login releases its DB transaction before hashing and checks current account/hash again before issuing a session. Further resource/load hardening remains open.

The known unreleased group-file discrepancy is corrected by applying the same item release and competition checks on group read paths; valid immutable-submission file access remains explicit. New group snapshots exclude removed/inactive students without rewriting old authorship. Negative tests cover these specific corrections.

## Independent Informatics privacy

Only an active eligible student starts training/circle participation. A facilitator's capabilities are local to the circle; no account-management, teacher grading or private-plan access is granted. Administrators have no routine private-plan browsing endpoint. Retained own plans can remain readable after membership ends, but cannot open current circle data or bypass write restrictions. The operator/database owner can technically access stored plaintext and backups: this is application privacy, **not end-to-end encryption**.

All freeform individual-practice discussion is denied before server gate, even a post labeled logistics. Started guidance/links are frozen. Events/notifications do not contain private reflections or gated bodies. Internal competition restrictions apply to new discussion. No software can prevent off-platform communication or prove every student's external-contest eligibility.

Reports have private acknowledgements and scoped admin review/resolution; hide/lock/approval actions are audited. School safeguarding, escalation response, consent and retention must be separately approved before real use. No public feed, messaging, arbitrary circle file upload or internet-public student leaderboard was introduced.

## Codeforces trust and consent

A handle is optional; lookup only proves public existence. School-admin approval records actor, time and an evidence method such as observing the student's logged-in account on their own device. The app never asks for Codeforces passwords or student API secrets. Approval is labeled **School-approved**, not certified by Codeforces. Changing an association requires new approval; canonical duplicate approvals are prevented. Participation is a separate default-off opt-in and withdrawal removes the ranked row without deleting private training.

Only active, opted-in, school-approved Informatics students enter this single-school authenticated leaderboard. DTOs omit email, personal IDs, grades and private notes. Disconnect removes live provider association/cache/observations; minimal approval audit metadata remains under the school's approved retention policy. Backup expiry is not immediate erasure. Full configurable retention/export tooling remains incomplete.

Provider calls are fixed-host/public-API only, no redirects, scraping or arbitrary link previews. Shared persisted leases pace calls conservatively and distinguish unavailable, malformed, invalid handle, stale cache and alias review. Instructor/facilitator roles cannot self-approve ownership. Live provider verification is still required.

## Storage, database and secrets

Supabase's service key can bypass Storage policies; keep it only in the backend secret store. The private object gateway rechecks current authorization, streams under private/no-store/nosniff restrictions and forces document downloads. Metadata and the private bucket alone do not replace the gateway. Use the supported opaque-secret API header contract; never put service/operator credentials in browser code, logs, screenshots or URLs shown to students.

Uploads are bounded to 8 MiB (incoming and normalized), 12 per target, initial 32 MiB/student and 128 MiB/staff, plus 500 MiB warning / 700 MiB global hard budget. Quota figures are application defaults, not provider entitlements. Typed configuration can preserve legacy quotas in test fixtures. Photo JPEG conversion is explicit; original metadata is stripped and transparency retains PNG. PDF signature checks are not antivirus/CDR. Files remain untrusted and source programs are not run.

Production requires PostgreSQL and private Supabase Storage, no SQLite/local fallback. Runtime is not schema owner and must not have superuser/DDL/role-creation/BYPASSRLS powers. Browser roles receive no application-schema usage. RLS allows backend DML but **does not identify V1 students**; FastAPI enforces row-level user permissions. Bootstrap/policy SQL and CI definitions are supplied but unexecuted against real PostgreSQL/Supabase here.

## Shared-device and operational boundaries

Editor recovery uses tab session storage, not an encrypted backup. Logout clears it; successful account change clears another student's recovery while preserving the current student's uncertain receipt. Shared-computer users must sign out and close tabs. A failed upload retains its File and retry key only while that page remains open; full page reload does not preserve a local File object.

No cloud account, deployment or real-data import was performed. The completed F05 encrypted DB-plus-object migration/backup/restore tools are **still pending**. Never adopt a frozen SQLite copy after V2 has accepted writes without reconciliation. Current cleanup never intentionally removes authoritative submissions/grades; school-approved lifecycle tooling and a tested restore remain release blockers.

Reference guidance: https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html ; https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html . References guide controls; they are not validation of this implementation.
