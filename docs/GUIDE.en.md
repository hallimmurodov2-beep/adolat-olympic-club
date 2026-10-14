# Adolat Olympic Club — M1 user guide

**Development checkpoint:** use synthetic accounts until school release gates pass. The sections below describe new Informatics workflows; the retained teaching guide follows. No full V2 completion or live deployment is implied.

## My Training

Use My Training to create a short cycle and one goal, add external HTTPS problem links, then record your own outcome, assistance used, brief reflection and next step. Notes are private, even inside a circle. A completed outcome is self-reported, not a school grade or proof of an independent accepted solution. Opening a link does not send your platform password to this application. Carry unfinished work to a new cycle or export your own plan data. No classroom, teacher or Codeforces link is needed after your school grants Informatics participation.

## Training Circles

A circle is a voluntary peer space, not a teacher classroom. The facilitator approves requests and schedules practice/debriefs; that role cannot read your private plan or change grades/accounts. Individual practice blocks all freeform discussion until the server gate. Collaborative study is explicitly labeled. The app cannot permit an activity forbidden by an external contest's rules or stop off-platform communication. Share only text you choose. Report a concern to the school moderator; removing/locking a member blocks further circle access.

## Codeforces and contests

Connecting a handle is optional. Read the public-metadata consent, submit your handle and wait for the school's ownership approval. The administrator may observe your logged-in Codeforces account on your own device; never give anyone a password. School approval is not certification by Codeforces. Leaderboard participation is a separate default-off choice and can be withdrawn. Only authenticated school users see the eligible approved/opted-in rows. Ratings are external public values, not school grades; unrated is not zero.

Upcoming contest cards show localized start time/timezone, duration, countdown, official link and data freshness. Check the official page for participation rules or changed times. An unavailable API shows a fallback, not invented events. Private training continues without the provider.

## Uploads and shared computers

Preview a photo before attaching it; JPEG conversion is optional, while PNG preserves diagrams/transparency. After an uncertain upload use Retry on the same open page. A browser reload cannot recreate the selected local File object. For submission uncertainty, use the receipt/retry controls rather than starting a duplicate attempt. Session recovery is not a backup. Sign out and close shared tabs.

---

## Retained teaching workflow guide


## First sign-in and language

Only invited users can register. Open the private invitation link supplied by the school, check the classroom and role, enter your display name, and choose a password of at least 12 characters. Do not forward an invitation: it is a single-use credential for the specified email address. New accounts default to Russian. Use **РУ / EN** on the sign-in/registration screen or in the sidebar to switch immediately. After sign-in, the language preference is saved to your account and used on other devices. The light/dark setting belongs to the current browser.

Teachers can provide Russian, English, or both versions of educational content. When the selected language is absent, the original appears with its language marked. Names, discussion messages, and uploaded documents are not automatically translated. The Help section is available inside the application.

## Administrator: prepare the workspace

The operator first applies migrations and creates the first administrator with the commands in the README. No account is created automatically when the server starts. In Administration, set the club name and school time zone. The initial time zone is UTC; change it before scheduling real lessons. The application shows the school time zone beside scheduling controls.

Invite teachers, then let each teacher create their subject classrooms. Administrators can oversee all rooms and assign existing student accounts to classrooms. Teachers can invite students to their own classrooms; the invitation fixes the role on the server. Teachers cannot create administrators or manage another teacher's classroom. Disable an account to revoke its sessions. Verify identity through the school before asking the operator to reset a forgotten password. This version does not send invitation emails or password-reset emails.

Archiving a classroom hides it from normal active-room views without erasing work. Use the archive confirmation deliberately; retention/deletion of school records is an operator-managed policy, not an automated student-data erasure feature.

## Teacher: create and assign work

1. Open **Classrooms**, create a classroom under Mathematics, Physics, or Informatics, and invite students. A classroom has one responsible teacher in this version. Add announcements and resources; attach only your own or appropriately licensed documents.
2. Open **Problem library** and create a problem in that classroom. Enter one or both language versions of the title and statement, choose/configure a topic, and record difficulty, source, year, tags, optional subtopic, hints, solution, expected format, and code examples. Save before adding statement attachments. A library problem must be published to be directly visible in the student library; hints and solutions remain teacher-controlled.
3. Create an **Assignment**. Select classroom-local problems or a reusable set, assign points and optional rubric criteria, choose the opening/deadline times, and confirm the enrolled classroom members. Competition participant rosters are configured separately. Check the schedule before saving. Publish the draft when ready. Assignments use snapshots of the problem text and its then-attached statement files; later library edits do not revise previously assigned text. Activity editing after creation is not included: recreate an unused draft to change its configuration.

Use `$...$` for inline mathematics and `$$...$$` for a displayed equation. The editor supports escaped text, basic emphasis/fenced code, and TeX rendering, not arbitrary HTML or a full word processor. Preview long statements and formulas on a narrow screen before class.

## Student: save and submit a solution

Open an assignment or active session from the dashboard. Select a released problem. For mathematics and physics, write a multi-step explanation with equations; images of handwritten work can be attached. For informatics, choose Python or C++ and type/paste source code. Syntax highlighting does not run the program.

The editor autosaves after a pause in typing. **Saved** means the server acknowledged the draft; an unsaved or failed-save message does not. A draft is not a submitted attempt. Use **Submit solution**, read the confirmation, and open the resulting receipt/attempt link. Repeated requests carrying the same submission identifier do not create duplicate attempts. Earlier attempts remain unchanged and can be revisited in Submissions.

When a connection fails, keep the tab open and preserve the text. The editor keeps a per-tab recovery copy, offers text export, retries temporary network failures, and offers **Retry**. Reconnecting, submitting, or further editing also retries a pending save. Recovery in browser storage is best-effort, not a substitute for server saving or an external copy. An expired deadline is not extended by a local draft or browser timer. Do not close the browser with unsaved work. Sign out on shared computers.

## Teacher: review and release feedback

Open **Submissions**, choose an attempt, and read the written work or source code and attachments. Award points directly or score each rubric criterion. Add feedback in either or both languages, choose reviewed/revision requested, and decide whether to release the review. Saving an unreleased review keeps the student's score and comments private. A review history records later changes and rejects stale simultaneous updates.

Students only see their own individual or assigned-team attempts. Released feedback appears in the attempt, notifications, and progress views. Progress is calculated from stored attempts and reviewed work; an unreviewed attempt does not count as a completed problem. Competition reviews remain sealed until the competition results are published, even when an individual review has been marked for release.

## Live classroom sessions

Create a session with prepared problems and an optional schedule/deadline. Start it from the session page. Students see the active session but not unreleased tasks. Release each problem when the class is ready; publish hints or solutions separately. The session page shows submitted attempts and requests for teacher assistance. Resolve a request after helping the student. Send a bilingual session announcement as needed.

Open **Presentation mode** for the projector. Select the task to display; the statement view suppresses hints and solutions to avoid accidental projection. Fullscreen uses the browser's fullscreen permission. Teacher controls and student pages synchronize through server-sent events; the connection badge reports live/reconnecting/polling/offline state. Automatic polling is the fallback. End the session with confirmation; the server then rejects further submissions.

## Group work

Create a group for a non-competition activity item and select enrolled teammates. Students use **Groups** to open their assigned workspace, discuss approaches, upload work, and edit one shared solution. Teachers can read the workspace, comment, and review its final submission.

This is revision-based collaboration, not character-by-character co-editing. If two people save an old revision, one save is rejected and both the local and server versions are displayed. Export or copy your changes before choosing the server version, or explicitly confirm keeping your own version against the newest revision. Never assume a teammate's text will be merged automatically. Saved revisions are available for recovery. The final team submission copies the saved server document and records the group members; the submitter cannot silently replace it with an unsaved client document.

Groups are private by default. A teacher can explicitly share a workspace read-only with other members of that classroom; unrelated classes remain excluded. During an eligible student's active competition, group access and collaboration endpoints are blocked. Group membership editing after creation is not provided in this version.

## Mock olympiads

Create a **Competition**, specify its start and end, participants, tasks, points, and rubric. Publish before the start. Eligible students see a dedicated individual-work interface and a countdown derived from server time. Tasks are hidden before the start. Submission and draft cutoffs are enforced in the database-backed API, not by the countdown alone.

Hints, solutions, and group collaboration are blocked during an active competition. This cannot remove material a student saw earlier or prevent communication outside the application. Select fresh tasks and supervise the room as for an ordinary school mock olympiad.

After the competition, review every submitted attempt and use **Publish results**. The server rejects early publication or publication while submissions remain unreviewed. There is no central public leaderboard. Results and feedback belong to the participant or assigned teacher.

## Files, privacy, and troubleshooting

Files are private and served only after authorization. Each file is limited to 8 MiB; each parent supports up to 12 attachments, with initial role quotas of 32 MiB/student and 128 MiB/staff, also subject to the shared storage budget. Check the current quota display. Allowed formats are PNG/JPEG/WebP, PDF, UTF-8 text, Python, and C++ source. Images are decoded and normalized. PDFs are not antivirus-scanned: treat unfamiliar files carefully. Attached submission files cannot be deleted through the normal file control.

An unavailable page may mean the teacher has not published it, your membership changed, or the account lacks permission. A save conflict means a newer revision exists, not that the old text has been deleted. A closed-submission error is based on server time. For forgotten passwords or an incorrect enrollment, contact the school administrator. Report persistent errors with the action and time, not your password, invitation token, or another student's work.
