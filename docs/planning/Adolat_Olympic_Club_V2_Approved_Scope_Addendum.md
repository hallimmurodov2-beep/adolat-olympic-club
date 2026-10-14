# Adolat Olympic Club — V2.0 Approved Scope Amendment

**Status:** Mandatory planning-scope amendment, approved in the user brief dated 14 October 2026. **No implementation has begun.**

**Companion:** `OlympiadOS_V2_Master_Blueprint.md` (existing 18-section plan). This amendment **takes precedence wherever the older blueprint differs**. Unchanged security, migration, data-preservation, teaching, localization, hosting, and no-AI provisions remain in force.

## 1. Scope decisions and precedence

| ID | Required change | Priority | Milestone |
|---|---|---|---|
| F25 | Rebrand all user-visible application surfaces to **Adolat Olympic Club**, using the supplied official school emblem and suitable derivative assets | P1 mandatory | Phase 0; verified in M1 |
| F26 | Student-initiated optional Codeforces-handle association, consent, validation and staff ownership approval | P1 mandatory | M1 |
| F27 | School-internal, **opt-in** Informatics Codeforces rating leaderboard | P1 mandatory | M1 |
| F28 | Upcoming regular Codeforces contest cards, start time, duration, countdown and link, with bounded caching and outage behavior | P1 mandatory | M1 |
| M1 | Early usable Informatics release: F06–F10 private training and circles, F25–F28, bilingual/mobile/authorization/provider-failure tests and a student pilot | P1 delivery gate | Before broad teaching UX polish and final school-data cutover |

**Interpretation of existing blueprint F11:** F11 remains an **optional P2 bounded refresh of external submission evidence** attached to training items, and may be disabled if needed. The mandatory F26–F28 profile, leaderboard and contest features must **not** be deferred under F11's optional-provider-refresh clause. An API outage may temporarily prevent *fresh* data, but must not disable training, cause a crash or justify shipping an unimplemented F26–F28.

**Revised exclusion:** An *internet-public or compulsory student rating leaderboard* is still excluded; a **school-authenticated and explicitly opt-in** Informatics leaderboard is now required. Automated claims of Codeforces ownership are not required; evidence-backed school-admin approval is the V2 solution.

## 2. Branding contract — F25

- Public UI product name: **Adolat Olympic Club**. This appears in sign-in/sign-up, onboarding, navigation/header, dashboard, relevant dialogs and email/document templates if present, browser `title`, page metadata, app manifest/icon labels (if supported), footer/help/about, error/loading states, and screenshots/manuals. Screen-reader labels and both RU/EN localizations follow suit.
- The supplied logo is an **181 × 148 pixel RGB PNG with an opaque white background**, not a transparent high-resolution vector. Retain the exact original unmodified as the master. Create proportion-preserving, high-quality reduced versions for nav/header and sign-in and practical favicon/tab/PWA sizes. Use an intentionally padded logo tile or carefully checked transparency conversion; do not claim the source has alpha. Ensure edge antialiasing and the thin circular stroke are not destroyed. Avoid needless enlargement; seek a higher-resolution/vector original later if available, without blocking V2.
- Design colors may be derived from the emblem's deep green, but must pass accessibility checks in light and dark themes. Branding must not compromise form contrast or focus visibility; logo images receive sensible text alternatives.
- Preserve existing package/database/migration/internal identifiers and compatible URLs/deep links where renaming would risk a needless V1 regression. The internal codebase may retain the engineering name `OlympiadOS`; it must not appear as the primary **user-facing** product name.
- Verify logo quality at actual CSS size on desktop/mobile and at favicon resolution; use a legible simplified crop/padded mark if a 16px favicon would otherwise fail.

## 3. Codeforces handle and approval — F26

### Student and staff workflow

1. A student with active Informatics participation may optionally enter a Codeforces handle. The app validates syntax, normalizes by the canonical `user.info` response, and retrieves **public** profile metadata through the official API only. A mere syntactically valid handle is not evidence of ownership.
2. The student separately opts into leaderboard publication (default **off**). They may withdraw at any time and disconnect their handle. The private My Training and Training Circles flows require neither a linked handle nor leaderboard participation.
3. School administrator approval is **required** before the handle can appear in the ranked school leaderboard. A teacher may approve only if explicitly delegated the necessary school-scoped permission; ordinary teachers, facilitators and students cannot self-approve.
4. A practical evidence method is a staff member observing the student logged into that Codeforces account on the student's own device, without sharing or entering the student's password into Adolat Olympic Club. A school-approved equivalent ownership demonstration may be used. The approver records the method, timestamp and staff identity. Mark the link **“School-approved”**, not **“verified by Codeforces”**.
5. Pending, rejected, unresolvable or conflicted handles are visibly labeled in the **owner-only settings view** and excluded from published leaderboard ranking. Administrators can revoke approval with an audit record. Changes to a linked handle must trigger fresh validation and reapproval; suspend the old leaderboard row until completion.
6. Enforce at most one current Codeforces account per student for this leaderboard and at most one **approved** school association per normalized canonical handle. Treat handle renaming and historic alias resolution as a review event, not silent transfer of an approved identity to someone else.

### Security and data boundaries

- No Codeforces passwords, authenticated browsing, OAuth simulation, profile scraping, arbitrary URL fetches, source-code extraction, or undocumented private APIs. Public `user.info` does not require a student API token.
- Keep the full approval and opt-in state behind authenticated, role-scoped FastAPI endpoints. Student-facing leaderboards must not expose email, grades, classroom rosters, private reflections or personal account identifiers unnecessarily. Avoid public indexing and unauthorized cross-school access.
- Only store minimum fields needed: user ID, normalized handle, consent state, opt-in state, approval state/actor/time/method, account status, last refresh/error, public rating cache. Revoking participation immediately removes the row; implement a documented disconnect/deletion behavior and retention policy.

### States

`not_connected`, `pending_validation`, `invalid_handle`, `pending_approval`, `approved_not_opted_in`, `approved_opted_in`, `rejected`, `revoked`, `provider_unavailable` (temporary status attached to a link). An outage must **not** be treated as a definitive invalid handle.

## 4. Opt-in Informatics leaderboard — F27

- Entry point: Informatics / Competitive Programming Hub, with a dashboard preview and a dedicated full leaderboard view. Visible only to authenticated, school-authorized viewers; published entries consist **only of actively enrolled Informatics students who opted in and have school-approved handles**.
- Per row: **canonical Codeforces handle**, **current rating**, **maximum rating**, **rank/title if returned**, **last successful rating refresh timestamp**, link to the official public profile, and a suitable *school-approved* marker where appropriate.
- Primary ordering: current rating descending; deterministic tie break by maximum rating descending and case-insensitive handle. Ratings missing because an account is unrated display **“Unrated”** and appear in a separate last section, not as invented 0. Missing rank/maxRating display **“—”**; timestamps distinguish a successful refresh from the account registration time.
- No manipulations of the Codeforces rating or alternative school rating formula. Codeforces official public values are authoritative, not a school grade or estimate.
- API: `user.info` (batch bounded eligible handles; public mode). Store validated, minimal snapshots; do not call Codeforces separately from every student browser request. Handle user-not-found, profile rename, malformed API envelope, network errors, timeouts and `FAILED` responses without losing consent/approval records.
- Cache refresh policy: initial design **every 6–12 hours** for eligible profiles, with server-coordinated refresh on demand when stale. Show last refresh and an explicit **“Data may be outdated”** state during outages. The exact interval can be tuned after testing within the published API limits.
- Show enough context that beginners understand opt-out and unrated accounts. Avoid shaming copy, public profile feeds, activity surveillance or mandatory rating comparisons.

## 5. Upcoming official contests — F28

- Entry point: prominently near the top of the Informatics hub, alongside current training and below/next to the primary training action; the full leaderboard should not crowd out My Training.
- Use public official `contest.list?gym=false`; select upcoming regular contests with `phase=BEFORE` and a valid `startTimeSeconds` in the future; sort by ascending start time; show roughly **3–5** nearest. Do not assume Gym/private/mashup access or official student eligibility.
- Cards show **name, localized start time and date, duration, countdown/time remaining, and official link** assembled only from the validated Codeforces contest ID (for example `https://codeforces.com/contest/{id}`). State times accurately for the student locale and timezone; avoid suggesting that a contest is open or registration is guaranteed.
- Calculate the countdown from an authoritative start timestamp in the browser. Updating the countdown **must not trigger new API calls**. Contest time may move; show the last data refresh and link students to the official contest page.
- Cache official contest data for about **15–30 minutes** initially, with a shared server-side cache and single-flight refresh. When unavailable, show previously retrieved contests clearly marked **stale** with their last refresh date; if there is no cached list, present an honest unavailable/try-again state plus a link to Codeforces contests rather than inventing events or start times.
- Basic filtering defaults to upcoming publicly listed regular contests, not personalized eligibility judgments or ratings-based recommendations.

## 6. Integration safety, provider budgets and deployment feasibility

Official Codeforces API documentation describes `user.info`, `contest.list`, a response envelope with `status=OK` or `FAILED`, public anonymous reads, and a documented cap of **one request per two seconds** across calls. Implement a **single shared server-side throttle** (e.g., conservative spacing of 3 seconds) across profile and contest refresh operations, deduplication/coalescing, timeouts, retry backoff, bounded concurrency and persisted or DB-coordinated operation leases if more than one worker is deployed. Separate failure state from business data; never treat stale as fresh. Source: https://codeforces.com/apiHelp and https://codeforces.com/apiHelp/methods and https://codeforces.com/apiHelp/objects (checked 14 Oct 2026).

Use the existing FastAPI backend as the only integration point. Do **not** make a browser directly poll the external provider for each page visit. Since free hosting may sleep or lack scheduled jobs, use cache-on-read/controlled on-demand refresh; a guaranteed always-running worker is **not** required. Existing F11 metadata syncing, if enabled, must share this same throttle.

### Intended backend structures

Extend planned `external_accounts` to track link, consent, opt-in and school-approval state. Existing `operation_leases` can coordinate provider access. Introduce a narrowly scoped cached Codeforces-profile representation (`codeforces_profile_cache` or equivalent validated columns) and cached contest metadata (`codeforces_contests` or bounded typed cache); index approval/opt-in eligibility and unique canonical handles. Keep `external_observations` optional for F11 only. Never use a privileged Supabase browser key; all mutations and reads are authorized by FastAPI.

### Intended API families (design names, subject to compatibility review)

- `PUT/DELETE /api/integrations/codeforces/account` — owner-only handle changes/disconnect, preserving explicit opt-in.
- `POST /api/integrations/codeforces/leaderboard-consent` — owner-only opt-in/out.
- `GET /api/informatics/codeforces/me` — handle state and owner-visible reason messages.
- `GET /api/informatics/leaderboard` — school-authenticated filtered, paginated cached ranking.
- `GET /api/informatics/contests/upcoming` — cached upcoming contest view with source/freshness timestamps.
- `GET/POST /api/admin/codeforces/approvals[/{id}]` — authorized staff queue, evidence metadata, approve/reject/revoke with auditing.

Use the present app's established CSRF/session rules, response errors, pagination, redaction and localization conventions. These are candidate route names; do not create duplicate routes with the pre-existing F11 integration family.

## 7. Revised dependency-ordered V2 implementation phases

| Phase | Deliverables and gate |
|---|---|
| **0 — Protect and brand** | Preserve V1; fix P0 unreleased attachment leak and other reproduced integrity bugs; retain regression suite; apply Adolat Olympic Club naming and logo derivatives early; establish new provider mocks and requirements for F26–F28. |
| **1 — Essential database/security foundation** | Make existing FastAPI/SQLAlchemy/Alembic path compatible with Supabase PostgreSQL, restricted runtime role, authenticated subject participation and new schema migrations. Configure a safe staging environment and minimal approved backup/restore for *any* real pilot data. No production V1 cutover yet. |
| **2A — My Training usable slice** | Private goal→external link queue→attempt/outcome→reflection→next-step loop, works with no Codeforces link or teacher. RU/EN, mobile, backend privacy tests. |
| **2B — Training Circles usable slice** | Student-created circles, membership, facilitators, shared scheduling and link coordination, strict pre-debrief gate, reporting/moderation, notifications and negative authorization tests. |
| **2C — Mandatory Codeforces hub slice** | Handle validation, school-admin approval and separate ranking opt-in; rating snapshots, leaderboard, upcoming contests, shared API throttling/cache, error/fallback states and school-private views. **May be developed alongside 2B**, but both must finish before the M1 gate. |
| **M1 — Early Informatics acceptance & pilot** | Combined My Training + Circles + handle flow + leaderboard + contests working end-to-end in an authorized staging/pilot environment. Test technical acceptance first; then run a small opt-in student pilot *before* later product polish. No unapproved school-data import or unprotected uploads. |
| **3 — Early feedback and iteration** | Fix friction from M1 pilot, confirm usability across novice/advanced students and RU/EN, preserve early scope acceptance; do not wait until final release to learn whether the hub is used. |
| **4 — Full storage and migration safety** | Complete Supabase private file storage, existing-data import/reconciliation, permission verification, production-grade backup/restore and rollback rehearsal. A migration failure blocks cutover, not the already-usable pilot training UI. |
| **5 — Mathematics/Physics enhancements** | Classroom enrollment, activity preparation and safe cloning, review/grading, handwriting/attachments, competition interruption handling; all V1 subject journeys remain regression-tested throughout development. |
| **6 — Cross-cutting reliability and polish** | Efficient realtime, pagination, mobile/accessibility, all locale keys, notifications, Render/Supabase free-tier load/performance, operational monitoring and deployment handoff. Optional F11 practice-item evidence refresh can remain here, with the shared Codeforces throttle. |
| **7 — Final release acceptance and reversible cutover** | Whole-app native-browser, API, authorization and migration tests, production staging verification, operator restore demonstration, school sign-off, small-cohort results and release documentation. No release with unresolved P0 or unverified data migration. |

**Safety rule:** The M1 pilot may collect actual student usage only after school privacy/consent and moderation approvals, secure hosting, database access controls and a tested pilot-data backup/restore path. If those prerequisites are unavailable, start with synthetic data and a supervised demonstration; do not call that a genuine student-adoption pilot.

## 8. Early Informatics milestone test matrix and release criteria

1. **Independent use:** Informatics student without any teacher/classroom, circle membership, or linked Codeforces account creates and completes a useful private cycle. A second student cannot read it.
2. **Circles:** Authorized student facilitator creates/manages a circle; another joins by consent; private plans remain secret; individual practice freeform discussion is inaccessible by all API/stream/export paths before the server gate; moderators can intervene.
3. **Codeforces approvals:** Pending/invalid/unverified handles do not enter rankings; ordinary students/facilitators cannot approve; one approved canonical handle cannot be claimed twice; changing or revoking a handle removes the associated row immediately.
4. **Opt-in:** No ranking entry appears by default; joining and withdrawal work without loss of unrelated private training data. A student's rating can be high but the student remains absent unless all eligibility, approval and consent gates pass.
5. **Rating accuracy:** Mock and controlled live official API responses populate handle, rating, max rating, rank and refresh time; unrated/missing fields never display as fabricated values. Ordering and tie-breaking tested.
6. **Contests:** Correct nearest-future filter and ordering, localized timezone, safe direct links, duration and countdown; clock rolls over at start; no per-second network refresh.
7. **Provider failures:** `FAILED`/call-limit, timeout, malformed JSON, unknown handle, rename/alias, 5xx and empty-cache cases produce useful states; other training workflows remain healthy; all traffic respects aggregate budget.
8. **Branding/localization:** Correct Adolat Olympic Club label/logo across login, dashboard, nav, browser/app title, RU/EN, dark/light, phone, keyboard, screen-reader alternatives and 16/32 px favicon where practical.
9. **V1 non-regression:** Existing Mathematics and Physics teaching, assignments, student work, submissions, grading, competition rules and privacy checks continue to pass on the targeted backend.
10. **Pilot validation:** Conduct a roughly 10–12-student voluntary, diverse Informatics pilot, ideally across four weeks. Reuse the earlier blueprint's provisional usage checks (week-four meaningful return, goal→practice→next-step completion, median weekly logging effort and independent facilitator success) but distinguish actual measured results from targets. Fix a critical usability failure before the broader V2 rollout.

The early gate is not passed merely by screenshots or endpoints: it requires integrated tests and an operational demonstration of every mandatory component. External API downtime permits a tested stale/unavailable fallback; it does **not** permit removing leaderboard/contest features from the build.

## 9. No-change decisions and explicit exclusions

- Retain native TypeScript frontend, FastAPI backend, SQLAlchemy/Alembic, V1 account/password/session continuity, Supabase PostgreSQL/private Storage strategy, and the same-origin low-cost deployment plan subject to its stated restrictions.
- Preserve Mathematics and Physics teacher-led processes and all existing student records. Critical permission and data-integrity fixes keep P0 precedence over all feature work.
- Preserve fully bilingual English/Russian behavior and school-appropriate privacy for minors.
- No internal online judge, Codeforces password collection, scraping, private API access, full data-history warehouse, automatic ownership certification, mandated leaderboard participation, public-facing student ranking, or application AI.
- Do not create a cloud account, write application code, provision infrastructure, run a migration, or deploy as part of this **planning confirmation**.

## 10. Before implementation starts

- [x] New required product name, logo, feature classes and priority accepted as planning inputs in the user brief.
- [ ] Verify school privacy/consent, moderator, ownership-approver and backup custodian before pilot with real students.
- [ ] Decide small operational defaults (profile/contest cache TTLs and pilot roster) within this bounded spec; they must not delay implementing the required UI/API behaviors.
- [ ] Translate this addendum into F25–F28 tickets and M1 acceptance tests; reconcile original F11 and original excluded-leaderboard wording as stated above.
- [ ] Obtain a better-resolution logo if easily available; **not** a release blocker as the supplied logo is accepted.
- [ ] Wait for explicit authorization to start implementation.
