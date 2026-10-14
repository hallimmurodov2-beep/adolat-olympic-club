# Security and privacy review notes

**This project has automated checks, not an independent security audit. Do not describe it as production-secure or legally compliant based on this delivery alone.** A school should conduct a staging review, decide retention and incident procedures, and confirm its applicable obligations before placing real minors’ information in the system.

## Implemented controls

Passwords use Argon2id. Database session values and invitation tokens are SHA-256 hashes, not the raw bearer tokens. Cookie sessions are HttpOnly, SameSite=Strict, revocable, and Secure in production. Authentication rotates the browser session. Password changes revoke other sessions and refresh the current session; account disabling revokes sessions on all devices. Wrong-credential responses do not disclose whether an account exists. Durable HMAC-keyed rate-limit counters protect authentication/invitation operations.

All authenticated unsafe requests require a session-bound HMAC CSRF header. Origin checks also apply to login and signup. No CORS access is enabled. Account registration requires a single-use invitation; neither registration, profiles, nor account activation can change the assigned role. Invitation previews put tokens in a POST body, not an access-log URL. The invitation link keeps the token in the browser fragment.

Classroom, group, submission, and file permissions are checked on the server. Data returned to students excludes unreleased teacher feedback/points and hidden hints/solutions. Problem, draft, document, and grade revisions use conflict checks. Submission attempts and attached-file references are immutable. Administrative mutations are audited without copying student solution bodies into logs.

Files are private, randomly named on disk, and served only after authorization. Limits are 8 MiB per stored file, 12 files per target, and 200 MiB per uploading user. JPEG/PNG/WebP images are decoded and re-encoded as PNG, stripping metadata including EXIF. PDF files get structural signature checks, not a malware certification. Plain UTF-8 text/Python/C++ files are stored without execution. SVG, HTML, executable formats, and invalid images are rejected. Downloads use nosniff and sandbox headers; non-images are downloaded as attachments.

The application escapes user HTML, limits input sizes and actual request-body bytes, uses a restrictive same-origin CSP, disables framing, and emits HSTS in production. SQL queries use bound ORM expressions. Rich text intentionally offers limited formatting rather than unsafe arbitrary HTML. Mathematical input uses a restricted local MathJax package configuration.

## Important limitations and deployment responsibilities

* No external penetration test, formal audit, browser-native CSP end-to-end test, sustained load test, or PostgreSQL runtime integration test was performed in the delivery environment. The navigation-restricted browser harness forwards real HTTP/SSE but cannot verify normal network navigation, native cookie attachment, downloads, or fullscreen policy. Test those in staging.
* No antivirus/CDR scanner, encrypted object-storage integration, malware-isolated document preview, or automated abuse-reporting system exists. Treat uploaded PDFs/source as untrusted; use updated endpoint software. The server never runs submissions. Configure an isolated judge before ever adding execution.
* No PostgreSQL RLS, per-tenant isolation, SSO, MFA, forgotten-password email service, or fine-grained delegated administrators are implemented. This is a single-school workspace. Keep the database private. The supplied Compose database owner is suitable for initial setup, not a least-privilege audited production role split; separate migration/runtime database roles during hardening.
* TLS terminates at your reverse proxy. Set an exact HTTPS APP_ORIGIN and a unique random APP_SECRET. Trust forwarded headers only from the actual proxy IP. Do not expose the development server, SQLite file, private upload directory, or database port to the Internet. Do not enable wildcard proxy trust to solve an IP configuration problem.
* Local theme/language preferences use browser localStorage. Unsaved editor recovery text stays in sessionStorage for the current tab and is removed after confirmed saves or explicit logout. It is not a guaranteed backup and is not encrypted against someone with access to the signed-in browser. Browser/session restore can preserve tab storage: teach shared-computer users to sign out and close tabs. Do not close a tab after a failed save until text is recovered/exported.
* Team participation/sharing is teacher-assigned. Once a teammate can read a shared document, software cannot stop them copying it elsewhere. Competition mode cannot retract already-disclosed materials or prohibit external messaging/devices.
* The application collects names, school emails, class membership, educational work, and reviews. It does not ask for dates of birth, home addresses, personal phone numbers, or public student profiles. Legal basis, guardian communication, data retention, student export/deletion, safeguarding, backups, breach handling, and jurisdiction-specific review remain school decisions. There is no automatic legal-compliance workflow.
* No automated deletion of educational work is enabled. The operator cleanup task only removes expired technical records and orphan files. Establish a supervised retention/export process; removing a classroom member is not deleting all their historical data.

## Operator checklist

Before real use: install updates; generate secrets; configure TLS/origin/proxy IP; use a clean database rather than repurposing demo records; invite rather than share accounts; verify class scopes with two teachers and unrelated students; test deadline/grade gates on PostgreSQL; inspect PDF/download behavior; restore a backup; confirm time zone and institutional privacy procedures; review audit and server logs without logging request bodies or credentials.

Save a coherent backup of **database + private uploads + required secret configuration**. Protect backups with encryption and restricted access. Test restores to an isolated environment, never into the only live database. For SQLite, stop the app before file-level backups, or use SQLite's online backup API; copying the main file alone while WAL is active is not a reliable backup.

Reference security guidance: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html and https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html . The implemented choices require application-specific review in addition to these references.
