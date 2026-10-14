# Delivery status — OlympiadOS 1.0

## What this delivery is

A runnable, integrated single-school application, supplied as source plus compiled browser assets. It uses a real relational database, authenticates actual persistent accounts, and runs the teacher/student workflows described below. Demonstration data is an explicitly invoked, separately labeled seed. There are no accounts hardcoded into authentication, no runtime AI services, no automatic translation, and no code-execution endpoint.

The stack differs from the preferred Next.js/Supabase starting point: unavailable registry access and services prevented validating that stack in the development sandbox. The delivered implementation is FastAPI/SQLAlchemy/Alembic with strict TypeScript, locally served CSS/MathJax/Prism, Babel, and Intl. The tested configuration is Python 3.13 with SQLite/WAL. PostgreSQL configuration, an explicit migration, offline-compiled PostgreSQL SQL, and Docker deployment files are included, but the PostgreSQL deployment was not run.

## Implemented and connected

| Workflow | Delivery behavior |
| --- | --- |
| Closed school access | First-admin CLI; single-use invitations binding email/role/classroom; login/logout/password changes; persistent preferred language; account disabling/session revocation; teacher/classroom and student/team access checks on the server. |
| Classrooms | Mathematics, physics, informatics; teacher-owned rooms; administrator enrollment; teacher student invitations; editable topics; announcements/resources with private files; archived-room history. |
| Problems and assignments | Bilingual authoring, search/filtering, subtopics/tags/source/year/difficulty, local LaTeX rendering, optional hints/solutions, statement attachments, reusable classroom-local sets, scheduled classroom assignments with frozen problem snapshots. |
| Live teaching | Teacher start/end and problem release; synchronized announcements, help requests and resolution, submitted-work monitor; projector statement view; genuine SSE replay and automatic polling fallback. |
| Individual work | Written/LaTeX reasoning and highlighted Python/C++ source; private autosaved revision-checked drafts; upload permissions; failed-save recovery/retry/export; confirmed idempotent submissions; immutable attempt history. |
| Group work | Teacher-assigned team and problem; private shared document, saved revisions, discussion and uploads; explicit stale-write conflict handling; optional classroom-local read-only sharing; final submission uses the saved server document and frozen participant membership. |
| Teacher review | Configurable point/rubric validation; private bilingual comments; revision requests; versioned grading; explicit feedback release; private student access. |
| Mock olympiads | Start/end and eligibility checks; hidden pre-start tasks; individual interface; server deadline enforcement for drafts, uploads, and submissions; competition-wide collaboration/hint restrictions; results gated until the end and completed review. |
| Progress | Database-derived participation, attempts, reviewed completion, topic scores, competition history, recent work and feedback; no fabricated numbers or public central leaderboard. |
| Bilingual/responsive interface | Russian default; Russian/English dictionaries and account-persisted switching; content fallback labels; Russian plurals; locale-aware values and school timezone; light/dark themes; mobile navigation and labeled controls. |

## Verification

**77 automated tests passed: 61 backend/native-stream tests and 16 bilingual browser workflows.** The exact commands are recorded in `TEST_REPORT.md`, with machine-readable JUnit reports beside it. Tests cover both languages and use temporary migrated databases. Browser workflows are real application rendering against the actual local API and database, with separate user sessions.

**Important browser-test qualification:** Chromium navigation is blocked by the managed policy of this sandbox. The executed browser workflows use the documented `BROWSER_BRIDGE=1` test harness: the actual UI runs in Chromium, while fetch and SSE are transported to the real local HTTP server using httpx. It does not return mock API data, bypass permissions, change browser policy, or ship with the application. Browser-native navigation, cookie delivery, CSP execution, download behavior, and projector fullscreen were **not** validated by this harness. Independent HTTP tests check server session behavior, authorization, response headers, streaming, and files. Normal-navigation Playwright tests are included for a deployment environment that permits them.

TypeScript strict compilation passed. Alembic upgrade/downgrade/re-upgrade and ORM schema parity were checked on SQLite. PostgreSQL offline migration SQL compiled; that does **not** establish PostgreSQL runtime compatibility or production readiness.

## Deliberate version-one limits

- Activities are configured when created; editing their dates, problem list, or roster after creation is not implemented. Delete/recreate an unused draft instead. Reusable sets are classroom-local and do not have a full editing/cloning interface. Each classroom has one responsible teacher; administrators can oversee all rooms.
- Teams use whole-document optimistic revisions, not CRDTs, simultaneous character-level merging, a whiteboard, or a diagram editor. Team membership cannot be edited after creation. Text supports a deliberately small safe formatting subset, not a full WYSIWYG document editor or PDF annotations.
- Programming work is submitted and reviewed manually. There is no execution, compiler, test runner, automatic judge, or sandbox. Teacher decisions—not hidden automated scoring—determine grades.
- No SMTP, external authentication, SSO, MFA, self-service password recovery, SIS integration, or import of copyrighted Olympiad archives. Operators verify identity and reset passwords. Invitations are copied and shared privately.
- Private files use a local filesystem volume, not Supabase/object storage. Type/size/image validation is implemented, but PDFs/source files are not antivirus- or content-disarm-scanned. Add malware scanning and institution-approved retention before accepting unfamiliar files widely.
- The application is single-school, not a multi-tenant SaaS. Authorization is implemented in server services; no PostgreSQL RLS policy is supplied. Browser users have no direct database or storage credentials.
- Administrative/workspace lists are intentionally bounded: activities and groups return up to 300, submission lists up to 1,000, group discussions up to 300 comments, and a group response includes the latest 50 document revisions. Library search is paginated; activity/set selection initially loads up to 100 classroom problems. Expand paging/export before a large archive. Progress endpoints also need load profiling for a large club.
- The local SQLite mode is intended for a single application worker. Multi-instance PostgreSQL, object storage, high-volume event delivery, background mail, formal audit export, scheduled retention/deletion, and disaster recovery automation need deployment work.
- The platform cannot erase materials a student has already seen or downloaded, prevent off-platform communication, or replace teacher supervision in a competition. Eligibility and access gates enforce the server's own boundaries only.
- Theme is browser-local; language is account-persistent. Student names, user discussion, and uploaded documents are never silently translated. Formula layout, screen-reader use, and keyboard behavior need a school-specific accessibility acceptance review; no WCAG certification is claimed.

## Before real students use it

Use a fresh database rather than the demo workspace. Configure secrets, HTTPS/origin, the school timezone, storage permissions, backups, monitoring, invitation delivery and account recovery procedures. Install dependencies from trusted registries and review their transitive versions. Run the normal browser suite and a PostgreSQL staging workflow; verify uploads, downloads, deadlines, native reconnection, concurrent edits, and restoration from backup on the actual infrastructure.

Obtain an independent security/privacy review and establish school policy for minors' records, staff access, consent where required, retention, deletion, and incident response. No public deployment or independently audited production-security claim is included in this delivery.
