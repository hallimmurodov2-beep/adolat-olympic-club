-- OFFLINE DDL COMPILATION ONLY; not executed, not a substitute for versioned migrations.


CREATE TABLE club_settings (
	id INTEGER NOT NULL, 
	name JSON NOT NULL, 
	timezone VARCHAR(60) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT singleton_settings CHECK (id = 1)
)

;


CREATE TABLE codeforces_contest_cache (
	id INTEGER NOT NULL, 
	contests JSON NOT NULL, 
	fetched_at BIGINT, 
	next_refresh_at BIGINT NOT NULL, 
	last_error VARCHAR(40), 
	PRIMARY KEY (id), 
	CONSTRAINT singleton_contest_cache CHECK (id = 1)
)

;


CREATE TABLE operation_leases (
	name VARCHAR(100) NOT NULL, 
	not_before BIGINT NOT NULL, 
	expires_at BIGINT NOT NULL, 
	owner VARCHAR(36) NOT NULL, 
	state JSON NOT NULL, 
	PRIMARY KEY (name)
)

;


CREATE TABLE rate_limits (
	key VARCHAR(64) NOT NULL, 
	"window" BIGINT NOT NULL, 
	count INTEGER NOT NULL, 
	PRIMARY KEY (key, "window")
)

;


CREATE TABLE storage_budget (
	id INTEGER NOT NULL, 
	committed_bytes BIGINT NOT NULL, 
	reserved_bytes BIGINT NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT valid_storage_budget CHECK (id = 1 AND committed_bytes >= 0 AND reserved_bytes >= 0)
)

;


CREATE TABLE subjects (
	id VARCHAR(30) NOT NULL, 
	name JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	display_name VARCHAR(100) NOT NULL, 
	password_hash TEXT NOT NULL, 
	role VARCHAR(12) NOT NULL, 
	locale VARCHAR(2) NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT valid_user_role CHECK (role IN ('admin','teacher','student')), 
	CONSTRAINT valid_locale CHECK (locale IN ('ru','en')), 
	UNIQUE (email)
)

;


CREATE TABLE audit_logs (
	id SERIAL NOT NULL, 
	actor_id VARCHAR(36), 
	action VARCHAR(60) NOT NULL, 
	detail JSON DEFAULT '{}' NOT NULL, 
	entity_id VARCHAR(64) NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
)

;

CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);


CREATE TABLE auth_sessions (
	token_hash VARCHAR(64) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	expires_at BIGINT NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id);

CREATE INDEX ix_auth_sessions_expires_at ON auth_sessions (expires_at);


CREATE TABLE classrooms (
	id VARCHAR(36) NOT NULL, 
	subject_id VARCHAR(30) NOT NULL, 
	teacher_id VARCHAR(36) NOT NULL, 
	name JSON NOT NULL, 
	description JSON NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(teacher_id) REFERENCES users (id)
)

;

CREATE INDEX ix_classrooms_teacher_id ON classrooms (teacher_id);

CREATE INDEX ix_classrooms_subject_id ON classrooms (subject_id);


CREATE TABLE external_accounts (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	provider VARCHAR(20) NOT NULL, 
	handle VARCHAR(24) NOT NULL, 
	normalized_handle VARCHAR(24) NOT NULL, 
	consent_at BIGINT NOT NULL, 
	leaderboard_opt_in BOOLEAN NOT NULL, 
	approval_status VARCHAR(24) NOT NULL, 
	approved_handle_key VARCHAR(24), 
	approved_by VARCHAR(36), 
	approved_at BIGINT, 
	approval_method VARCHAR(40), 
	last_error VARCHAR(40), 
	last_attempt_at BIGINT, 
	last_success_at BIGINT, 
	next_refresh_at BIGINT NOT NULL, 
	version INTEGER NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_external_account_owner UNIQUE (user_id, provider), 
	CONSTRAINT external_approval_state CHECK (approval_status IN ('pending_validation','invalid_handle','pending_approval','approved','rejected','revoked','conflicted')), 
	CONSTRAINT approved_handle_consistency CHECK ((approval_status = 'approved' AND approved_handle_key IS NOT NULL) OR (approval_status != 'approved' AND approved_handle_key IS NULL)), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (approved_handle_key), 
	FOREIGN KEY(approved_by) REFERENCES users (id)
)

;

CREATE INDEX ix_external_accounts_normalized_handle ON external_accounts (normalized_handle);

CREATE INDEX ix_external_accounts_user_id ON external_accounts (user_id);


CREATE TABLE notifications (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(50) NOT NULL, 
	title JSON NOT NULL, 
	link VARCHAR(200) NOT NULL, 
	read BOOLEAN NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE INDEX ix_notifications_user_id ON notifications (user_id);


CREATE TABLE subject_memberships (
	subject_id VARCHAR(30) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	active BOOLEAN NOT NULL, 
	joined_at BIGINT NOT NULL, 
	source VARCHAR(30) NOT NULL, 
	PRIMARY KEY (subject_id, user_id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;


CREATE TABLE topics (
	id VARCHAR(36) NOT NULL, 
	subject_id VARCHAR(30) NOT NULL, 
	name JSON NOT NULL, 
	created_by VARCHAR(36), 
	PRIMARY KEY (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE INDEX ix_topics_subject_id ON topics (subject_id);


CREATE TABLE training_circles (
	id VARCHAR(36) NOT NULL, 
	subject_id VARCHAR(30) NOT NULL, 
	created_by VARCHAR(36) NOT NULL, 
	name JSON NOT NULL, 
	description JSON NOT NULL, 
	discoverable BOOLEAN NOT NULL, 
	archived BOOLEAN NOT NULL, 
	locked BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	created_at BIGINT NOT NULL, 
	updated_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(subject_id) REFERENCES subjects (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;

CREATE INDEX ix_training_circles_created_by ON training_circles (created_by);


CREATE TABLE activities (
	id VARCHAR(36) NOT NULL, 
	classroom_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(12) NOT NULL, 
	title JSON NOT NULL, 
	description JSON NOT NULL, 
	starts_at BIGINT, 
	ends_at BIGINT, 
	duration_minutes INTEGER NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	results_published BOOLEAN NOT NULL, 
	announcement JSON NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT activity_kind CHECK (kind IN ('assignment','session','competition')), 
	CONSTRAINT activity_status CHECK (status IN ('draft','published','live','ended')), 
	CONSTRAINT activity_time_order CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id)
)

;

CREATE INDEX ix_activities_classroom_id ON activities (classroom_id);

CREATE INDEX ix_activities_ends_at ON activities (ends_at);

CREATE INDEX ix_activities_kind ON activities (kind);


CREATE TABLE announcements (
	id VARCHAR(36) NOT NULL, 
	classroom_id VARCHAR(36) NOT NULL, 
	author_id VARCHAR(36) NOT NULL, 
	body JSON NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
)

;

CREATE INDEX ix_announcements_classroom_id ON announcements (classroom_id);


CREATE TABLE circle_members (
	circle_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	role VARCHAR(15) NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	transfer_consent BOOLEAN NOT NULL, 
	joined_at BIGINT NOT NULL, 
	PRIMARY KEY (circle_id, user_id), 
	CONSTRAINT circle_role CHECK (role IN ('member','facilitator')), 
	CONSTRAINT circle_member_status CHECK (status IN ('pending','active')), 
	FOREIGN KEY(circle_id) REFERENCES training_circles (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE INDEX ix_circle_member_user ON circle_members (user_id, status);


CREATE TABLE codeforces_profile_cache (
	account_id VARCHAR(36) NOT NULL, 
	handle VARCHAR(24) NOT NULL, 
	rating INTEGER, 
	max_rating INTEGER, 
	rank VARCHAR(80), 
	registration_time BIGINT, 
	max_rank VARCHAR(80), 
	fetched_at BIGINT NOT NULL, 
	PRIMARY KEY (account_id), 
	FOREIGN KEY(account_id) REFERENCES external_accounts (id) ON DELETE CASCADE
)

;


CREATE TABLE external_observations (
	id VARCHAR(36) NOT NULL, 
	account_id VARCHAR(36) NOT NULL, 
	submission_id BIGINT NOT NULL, 
	problem_key VARCHAR(80) NOT NULL, 
	verdict VARCHAR(40) NOT NULL, 
	external_at BIGINT NOT NULL, 
	observed_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_external_observation UNIQUE (account_id, submission_id), 
	FOREIGN KEY(account_id) REFERENCES external_accounts (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_external_observations_account_id ON external_observations (account_id);


CREATE TABLE invitations (
	id VARCHAR(36) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	role VARCHAR(12) NOT NULL, 
	classroom_id VARCHAR(36), 
	created_by VARCHAR(36) NOT NULL, 
	expires_at BIGINT NOT NULL, 
	accepted_at BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT valid_invite_role CHECK (role IN ('teacher','student')), 
	UNIQUE (token_hash), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
)

;


CREATE TABLE memberships (
	classroom_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	joined_at BIGINT NOT NULL, 
	PRIMARY KEY (classroom_id, user_id), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
)

;


CREATE TABLE problem_sets (
	id VARCHAR(36) NOT NULL, 
	classroom_id VARCHAR(36) NOT NULL, 
	title JSON NOT NULL, 
	description JSON NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id)
)

;

CREATE INDEX ix_problem_sets_classroom_id ON problem_sets (classroom_id);


CREATE TABLE problems (
	id VARCHAR(36) NOT NULL, 
	classroom_id VARCHAR(36) NOT NULL, 
	author_id VARCHAR(36) NOT NULL, 
	topic_id VARCHAR(36), 
	title JSON NOT NULL, 
	statement JSON NOT NULL, 
	subtopic JSON NOT NULL, 
	hints JSON NOT NULL, 
	solution JSON NOT NULL, 
	examples JSON NOT NULL, 
	difficulty INTEGER NOT NULL, 
	source VARCHAR(300) NOT NULL, 
	year INTEGER, 
	tags JSON NOT NULL, 
	format VARCHAR(12) NOT NULL, 
	published BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	search_text TEXT NOT NULL, 
	created_at BIGINT NOT NULL, 
	updated_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT problem_difficulty CHECK (difficulty BETWEEN 1 AND 5), 
	CONSTRAINT problem_format CHECK (format IN ('written','code')), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id), 
	FOREIGN KEY(author_id) REFERENCES users (id), 
	FOREIGN KEY(topic_id) REFERENCES topics (id)
)

;

CREATE INDEX ix_problems_classroom_id ON problems (classroom_id);

CREATE INDEX ix_problems_topic_id ON problems (topic_id);


CREATE TABLE resources (
	id VARCHAR(36) NOT NULL, 
	classroom_id VARCHAR(36) NOT NULL, 
	topic_id VARCHAR(36), 
	title JSON NOT NULL, 
	body JSON NOT NULL, 
	url TEXT, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id), 
	FOREIGN KEY(topic_id) REFERENCES topics (id)
)

;

CREATE INDEX ix_resources_classroom_id ON resources (classroom_id);


CREATE TABLE stored_files (
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	classroom_id VARCHAR(36) NOT NULL, 
	target_kind VARCHAR(12) NOT NULL, 
	target_id VARCHAR(36) NOT NULL, 
	filename VARCHAR(180) NOT NULL, 
	media_type VARCHAR(80) NOT NULL, 
	size BIGINT NOT NULL, 
	created_at BIGINT NOT NULL, 
	storage_backend VARCHAR(15) DEFAULT 'local' NOT NULL, 
	object_key VARCHAR(150), 
	sha256 VARCHAR(64), 
	PRIMARY KEY (id), 
	CONSTRAINT file_target_kind CHECK (target_kind IN ('problem','resource','draft','group')), 
	CONSTRAINT file_size CHECK (size > 0 AND size <= 8388608), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id)
)

;

CREATE INDEX ix_stored_files_owner_id ON stored_files (owner_id);

CREATE INDEX ix_stored_files_target_id ON stored_files (target_id);

CREATE INDEX ix_stored_files_classroom_id ON stored_files (classroom_id);


CREATE TABLE training_cycles (
	id VARCHAR(36) NOT NULL, 
	circle_id VARCHAR(36), 
	owner_id VARCHAR(36), 
	title JSON NOT NULL, 
	guidance JSON NOT NULL, 
	links JSON NOT NULL, 
	starts_at BIGINT NOT NULL, 
	ends_at BIGINT NOT NULL, 
	practice_starts_at BIGINT, 
	practice_ends_at BIGINT, 
	discussion_opens_at BIGINT, 
	mode VARCHAR(20) NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at BIGINT NOT NULL, 
	updated_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT cycle_owner_xor CHECK ((circle_id IS NULL AND owner_id IS NOT NULL) OR (circle_id IS NOT NULL AND owner_id IS NULL)), 
	CONSTRAINT cycle_time_order CHECK (ends_at > starts_at), 
	CONSTRAINT cycle_mode CHECK (mode IN ('individual','collaborative')), 
	CONSTRAINT cycle_status CHECK (status IN ('draft','published','cancelled')), 
	CONSTRAINT circle_practice_times CHECK (circle_id IS NULL OR (practice_starts_at IS NOT NULL AND practice_ends_at IS NOT NULL AND discussion_opens_at IS NOT NULL AND practice_ends_at > practice_starts_at)), 
	CONSTRAINT individual_discussion_gate CHECK (circle_id IS NULL OR mode != 'individual' OR discussion_opens_at >= practice_ends_at), 
	FOREIGN KEY(circle_id) REFERENCES training_circles (id), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
)

;

CREATE INDEX ix_training_cycles_owner_id ON training_cycles (owner_id);

CREATE INDEX ix_training_cycles_circle_id ON training_cycles (circle_id);


CREATE TABLE upload_intents (
	id VARCHAR(36) NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	client_id VARCHAR(36) NOT NULL, 
	target_kind VARCHAR(12) NOT NULL, 
	target_id VARCHAR(36) NOT NULL, 
	classroom_id VARCHAR(36) NOT NULL, 
	object_key VARCHAR(150) NOT NULL, 
	backend VARCHAR(15) NOT NULL, 
	reserved_bytes BIGINT NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	media_type VARCHAR(80) NOT NULL, 
	filename VARCHAR(180) NOT NULL, 
	state VARCHAR(15) NOT NULL, 
	created_at BIGINT NOT NULL, 
	expires_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_upload_intent_client UNIQUE (owner_id, client_id), 
	CONSTRAINT upload_intent_state CHECK (state IN ('reserved','uploading','ready','failed','deleting','cleaned')), 
	FOREIGN KEY(owner_id) REFERENCES users (id), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id)
)

;

CREATE INDEX ix_upload_intent_expiry ON upload_intents (state, expires_at);

CREATE INDEX ix_upload_intents_owner_id ON upload_intents (owner_id);


CREATE TABLE activity_items (
	id VARCHAR(36) NOT NULL, 
	activity_id VARCHAR(36) NOT NULL, 
	problem_id VARCHAR(36) NOT NULL, 
	snapshot JSON NOT NULL, 
	position INTEGER NOT NULL, 
	points FLOAT NOT NULL, 
	rubric JSON NOT NULL, 
	released_at BIGINT, 
	hints_released BOOLEAN NOT NULL, 
	solution_released BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_activity_problem UNIQUE (activity_id, problem_id), 
	CONSTRAINT item_points CHECK (points > 0 AND points <= 1000), 
	FOREIGN KEY(activity_id) REFERENCES activities (id) ON DELETE CASCADE, 
	FOREIGN KEY(problem_id) REFERENCES problems (id)
)

;

CREATE INDEX ix_activity_items_problem_id ON activity_items (problem_id);

CREATE INDEX ix_activity_items_activity_id ON activity_items (activity_id);


CREATE TABLE help_requests (
	id VARCHAR(36) NOT NULL, 
	activity_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	body VARCHAR(1000) NOT NULL, 
	resolved BOOLEAN NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(activity_id) REFERENCES activities (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE INDEX ix_help_requests_activity_id ON help_requests (activity_id);


CREATE TABLE participants (
	activity_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (activity_id, user_id), 
	FOREIGN KEY(activity_id) REFERENCES activities (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE peer_posts (
	id VARCHAR(36) NOT NULL, 
	cycle_id VARCHAR(36) NOT NULL, 
	author_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	body JSON NOT NULL, 
	hidden BOOLEAN NOT NULL, 
	client_id VARCHAR(36) NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_peer_post_mutation UNIQUE (author_id, client_id), 
	CONSTRAINT peer_post_kind CHECK (kind IN ('help','explanation','logistics')), 
	FOREIGN KEY(cycle_id) REFERENCES training_cycles (id), 
	FOREIGN KEY(author_id) REFERENCES users (id)
)

;

CREATE INDEX ix_peer_posts_cursor ON peer_posts (cycle_id, created_at, id);

CREATE INDEX ix_peer_posts_cycle_id ON peer_posts (cycle_id);


CREATE TABLE set_items (
	set_id VARCHAR(36) NOT NULL, 
	problem_id VARCHAR(36) NOT NULL, 
	position INTEGER NOT NULL, 
	PRIMARY KEY (set_id, problem_id), 
	FOREIGN KEY(set_id) REFERENCES problem_sets (id) ON DELETE CASCADE, 
	FOREIGN KEY(problem_id) REFERENCES problems (id)
)

;


CREATE TABLE training_plans (
	id VARCHAR(36) NOT NULL, 
	cycle_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	goal JSON NOT NULL, 
	review JSON NOT NULL, 
	next_step JSON NOT NULL, 
	context JSON NOT NULL, 
	version INTEGER NOT NULL, 
	created_at BIGINT NOT NULL, 
	updated_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_training_plan_owner UNIQUE (cycle_id, user_id), 
	FOREIGN KEY(cycle_id) REFERENCES training_cycles (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE INDEX ix_training_plans_user_id ON training_plans (user_id);

CREATE INDEX ix_training_plans_cycle_id ON training_plans (cycle_id);


CREATE TABLE drafts (
	activity_item_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	content TEXT NOT NULL, 
	language VARCHAR(12) NOT NULL, 
	revision INTEGER NOT NULL, 
	updated_at BIGINT NOT NULL, 
	PRIMARY KEY (activity_item_id, user_id), 
	FOREIGN KEY(activity_item_id) REFERENCES activity_items (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE groups (
	id VARCHAR(36) NOT NULL, 
	classroom_id VARCHAR(36) NOT NULL, 
	activity_item_id VARCHAR(36) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	shared BOOLEAN NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id), 
	FOREIGN KEY(activity_item_id) REFERENCES activity_items (id)
)

;

CREATE INDEX ix_groups_classroom_id ON groups (classroom_id);

CREATE INDEX ix_groups_activity_item_id ON groups (activity_item_id);


CREATE TABLE moderation_reports (
	id VARCHAR(36) NOT NULL, 
	reporter_id VARCHAR(36) NOT NULL, 
	circle_id VARCHAR(36) NOT NULL, 
	post_id VARCHAR(36), 
	reason VARCHAR(40) NOT NULL, 
	detail VARCHAR(1000) NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	resolution VARCHAR(1000) NOT NULL, 
	resolved_by VARCHAR(36), 
	resolved_at BIGINT, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT report_status CHECK (status IN ('open','resolved')), 
	FOREIGN KEY(reporter_id) REFERENCES users (id), 
	FOREIGN KEY(circle_id) REFERENCES training_circles (id), 
	FOREIGN KEY(post_id) REFERENCES peer_posts (id), 
	FOREIGN KEY(resolved_by) REFERENCES users (id)
)

;


CREATE TABLE training_items (
	id VARCHAR(36) NOT NULL, 
	plan_id VARCHAR(36) NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	url VARCHAR(2000) NOT NULL, 
	provider VARCHAR(20), 
	problem_key VARCHAR(80), 
	status VARCHAR(20) NOT NULL, 
	position INTEGER NOT NULL, 
	carried_from_id VARCHAR(36), 
	client_id VARCHAR(36) NOT NULL, 
	version INTEGER NOT NULL, 
	created_at BIGINT NOT NULL, 
	updated_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_training_item_mutation UNIQUE (plan_id, client_id), 
	CONSTRAINT training_item_status CHECK (status IN ('not_started','attempted','revisit','completed')), 
	FOREIGN KEY(plan_id) REFERENCES training_plans (id) ON DELETE CASCADE, 
	FOREIGN KEY(carried_from_id) REFERENCES training_items (id) ON DELETE SET NULL
)

;

CREATE INDEX ix_training_items_plan_id ON training_items (plan_id);


CREATE TABLE document_revisions (
	id VARCHAR(36) NOT NULL, 
	group_id VARCHAR(36) NOT NULL, 
	revision INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	language VARCHAR(12) NOT NULL, 
	author_id VARCHAR(36) NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_group_revision UNIQUE (group_id, revision), 
	FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
	FOREIGN KEY(author_id) REFERENCES users (id)
)

;

CREATE INDEX ix_document_revisions_group_id ON document_revisions (group_id);


CREATE TABLE events (
	id SERIAL NOT NULL, 
	classroom_id VARCHAR(36), 
	user_id VARCHAR(36), 
	group_id VARCHAR(36), 
	kind VARCHAR(40) NOT NULL, 
	entity_id VARCHAR(36) NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(classroom_id) REFERENCES classrooms (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
)

;

CREATE INDEX ix_events_user_id ON events (user_id);

CREATE INDEX ix_events_created_at ON events (created_at);

CREATE INDEX ix_events_classroom_id ON events (classroom_id);


CREATE TABLE group_comments (
	id VARCHAR(36) NOT NULL, 
	group_id VARCHAR(36) NOT NULL, 
	author_id VARCHAR(36) NOT NULL, 
	body TEXT NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
	FOREIGN KEY(author_id) REFERENCES users (id)
)

;

CREATE INDEX ix_group_comments_group_id ON group_comments (group_id);


CREATE TABLE group_documents (
	group_id VARCHAR(36) NOT NULL, 
	content TEXT NOT NULL, 
	language VARCHAR(12) NOT NULL, 
	revision INTEGER NOT NULL, 
	updated_at BIGINT NOT NULL, 
	updated_by VARCHAR(36), 
	PRIMARY KEY (group_id), 
	FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
	FOREIGN KEY(updated_by) REFERENCES users (id)
)

;


CREATE TABLE group_members (
	group_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (group_id, user_id), 
	FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;


CREATE TABLE practice_entries (
	id VARCHAR(36) NOT NULL, 
	item_id VARCHAR(36) NOT NULL, 
	author_id VARCHAR(36) NOT NULL, 
	outcome VARCHAR(20) NOT NULL, 
	assistance VARCHAR(20) NOT NULL, 
	reflection JSON NOT NULL, 
	next_step JSON NOT NULL, 
	occurred_at BIGINT NOT NULL, 
	created_at BIGINT NOT NULL, 
	client_id VARCHAR(36) NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_practice_entry_mutation UNIQUE (author_id, client_id), 
	CONSTRAINT entry_outcome CHECK (outcome IN ('not_started','attempted','revisit','completed')), 
	CONSTRAINT entry_assistance CHECK (assistance IN ('independent','hints','editorial','peer')), 
	FOREIGN KEY(item_id) REFERENCES training_items (id) ON DELETE CASCADE, 
	FOREIGN KEY(author_id) REFERENCES users (id)
)

;

CREATE INDEX ix_practice_entries_item_id ON practice_entries (item_id);

CREATE INDEX ix_practice_entries_author_id ON practice_entries (author_id);


CREATE TABLE submissions (
	id VARCHAR(36) NOT NULL, 
	activity_item_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	group_id VARCHAR(36), 
	owner_key VARCHAR(50) NOT NULL, 
	client_id VARCHAR(36) NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	attempt INTEGER NOT NULL, 
	content TEXT NOT NULL, 
	language VARCHAR(12) NOT NULL, 
	group_revision INTEGER, 
	created_at BIGINT NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	score FLOAT, 
	criterion_scores JSON NOT NULL, 
	feedback JSON NOT NULL, 
	released BOOLEAN NOT NULL, 
	graded_by VARCHAR(36), 
	graded_at BIGINT, 
	grade_version INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_submission_idempotency UNIQUE (user_id, client_id), 
	CONSTRAINT uq_submission_attempt UNIQUE (activity_item_id, owner_key, attempt), 
	CONSTRAINT submission_status CHECK (status IN ('submitted','reviewed','revision_requested')), 
	CONSTRAINT submission_score CHECK (score IS NULL OR score >= 0), 
	FOREIGN KEY(activity_item_id) REFERENCES activity_items (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id), 
	FOREIGN KEY(graded_by) REFERENCES users (id)
)

;

CREATE INDEX ix_submissions_user_id ON submissions (user_id);

CREATE INDEX ix_submissions_activity_item_id ON submissions (activity_item_id);

CREATE INDEX ix_submissions_group_id ON submissions (group_id);


CREATE TABLE grade_revisions (
	id VARCHAR(36) NOT NULL, 
	submission_id VARCHAR(36) NOT NULL, 
	teacher_id VARCHAR(36) NOT NULL, 
	version INTEGER NOT NULL, 
	score FLOAT NOT NULL, 
	criterion_scores JSON NOT NULL, 
	feedback JSON NOT NULL, 
	status VARCHAR(24) NOT NULL, 
	released BOOLEAN NOT NULL, 
	created_at BIGINT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(submission_id) REFERENCES submissions (id), 
	FOREIGN KEY(teacher_id) REFERENCES users (id)
)

;

CREATE INDEX ix_grade_revisions_submission_id ON grade_revisions (submission_id);


CREATE TABLE submission_files (
	submission_id VARCHAR(36) NOT NULL, 
	file_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (submission_id, file_id), 
	FOREIGN KEY(submission_id) REFERENCES submissions (id) ON DELETE CASCADE, 
	FOREIGN KEY(file_id) REFERENCES stored_files (id)
)

;


CREATE TABLE submission_members (
	submission_id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (submission_id, user_id), 
	FOREIGN KEY(submission_id) REFERENCES submissions (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;
