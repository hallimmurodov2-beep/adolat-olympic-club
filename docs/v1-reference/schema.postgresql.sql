-- OFFLINE DIALECT COMPILATION ONLY. Not executed against PostgreSQL in this environment.
-- Apply migrations with the operator CLI; this is a review artifact, not a second migration source.
BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> bb2030abeaf7

CREATE TABLE club_settings (
    id SERIAL NOT NULL, 
    name JSON NOT NULL, 
    timezone VARCHAR(60) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT singleton_settings CHECK (id = 1)
);

CREATE TABLE rate_limits (
    key VARCHAR(64) NOT NULL, 
    "window" BIGINT NOT NULL, 
    count INTEGER NOT NULL, 
    PRIMARY KEY (key, "window")
);

CREATE TABLE subjects (
    id VARCHAR(30) NOT NULL, 
    name JSON NOT NULL, 
    PRIMARY KEY (id)
);

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
    CONSTRAINT valid_locale CHECK (locale IN ('ru','en')), 
    CONSTRAINT valid_user_role CHECK (role IN ('admin','teacher','student')), 
    UNIQUE (email)
);

CREATE TABLE audit_logs (
    id SERIAL NOT NULL, 
    actor_id VARCHAR(36), 
    action VARCHAR(60) NOT NULL, 
    entity_id VARCHAR(64) NOT NULL, 
    created_at BIGINT NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(actor_id) REFERENCES users (id)
);

CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

CREATE TABLE auth_sessions (
    token_hash VARCHAR(64) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    expires_at BIGINT NOT NULL, 
    created_at BIGINT NOT NULL, 
    PRIMARY KEY (token_hash), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_auth_sessions_expires_at ON auth_sessions (expires_at);

CREATE INDEX ix_auth_sessions_user_id ON auth_sessions (user_id);

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
);

CREATE INDEX ix_classrooms_subject_id ON classrooms (subject_id);

CREATE INDEX ix_classrooms_teacher_id ON classrooms (teacher_id);

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
);

CREATE INDEX ix_notifications_user_id ON notifications (user_id);

CREATE TABLE topics (
    id VARCHAR(36) NOT NULL, 
    subject_id VARCHAR(30) NOT NULL, 
    name JSON NOT NULL, 
    created_by VARCHAR(36), 
    PRIMARY KEY (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    FOREIGN KEY(subject_id) REFERENCES subjects (id)
);

CREATE INDEX ix_topics_subject_id ON topics (subject_id);

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
);

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
    FOREIGN KEY(author_id) REFERENCES users (id), 
    FOREIGN KEY(classroom_id) REFERENCES classrooms (id)
);

CREATE INDEX ix_announcements_classroom_id ON announcements (classroom_id);

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
    FOREIGN KEY(classroom_id) REFERENCES classrooms (id), 
    FOREIGN KEY(created_by) REFERENCES users (id), 
    UNIQUE (token_hash)
);

CREATE TABLE memberships (
    classroom_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    joined_at BIGINT NOT NULL, 
    PRIMARY KEY (classroom_id, user_id), 
    FOREIGN KEY(classroom_id) REFERENCES classrooms (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE problem_sets (
    id VARCHAR(36) NOT NULL, 
    classroom_id VARCHAR(36) NOT NULL, 
    title JSON NOT NULL, 
    description JSON NOT NULL, 
    created_at BIGINT NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(classroom_id) REFERENCES classrooms (id)
);

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
    CONSTRAINT problem_format CHECK (format IN ('written','code')), 
    CONSTRAINT problem_difficulty CHECK (difficulty BETWEEN 1 AND 5), 
    FOREIGN KEY(author_id) REFERENCES users (id), 
    FOREIGN KEY(classroom_id) REFERENCES classrooms (id), 
    FOREIGN KEY(topic_id) REFERENCES topics (id)
);

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
);

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
    PRIMARY KEY (id), 
    CONSTRAINT file_target_kind CHECK (target_kind IN ('problem','resource','draft','group')), 
    CONSTRAINT file_size CHECK (size > 0 AND size <= 8388608), 
    FOREIGN KEY(classroom_id) REFERENCES classrooms (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_stored_files_classroom_id ON stored_files (classroom_id);

CREATE INDEX ix_stored_files_owner_id ON stored_files (owner_id);

CREATE INDEX ix_stored_files_target_id ON stored_files (target_id);

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
    CONSTRAINT item_points CHECK (points > 0 AND points <= 1000), 
    FOREIGN KEY(activity_id) REFERENCES activities (id) ON DELETE CASCADE, 
    FOREIGN KEY(problem_id) REFERENCES problems (id), 
    CONSTRAINT uq_activity_problem UNIQUE (activity_id, problem_id)
);

CREATE INDEX ix_activity_items_activity_id ON activity_items (activity_id);

CREATE INDEX ix_activity_items_problem_id ON activity_items (problem_id);

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
);

CREATE INDEX ix_help_requests_activity_id ON help_requests (activity_id);

CREATE TABLE participants (
    activity_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (activity_id, user_id), 
    FOREIGN KEY(activity_id) REFERENCES activities (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE set_items (
    set_id VARCHAR(36) NOT NULL, 
    problem_id VARCHAR(36) NOT NULL, 
    position INTEGER NOT NULL, 
    PRIMARY KEY (set_id, problem_id), 
    FOREIGN KEY(problem_id) REFERENCES problems (id), 
    FOREIGN KEY(set_id) REFERENCES problem_sets (id) ON DELETE CASCADE
);

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
);

CREATE TABLE groups (
    id VARCHAR(36) NOT NULL, 
    classroom_id VARCHAR(36) NOT NULL, 
    activity_item_id VARCHAR(36) NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    shared BOOLEAN NOT NULL, 
    created_at BIGINT NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(activity_item_id) REFERENCES activity_items (id), 
    FOREIGN KEY(classroom_id) REFERENCES classrooms (id)
);

CREATE INDEX ix_groups_activity_item_id ON groups (activity_item_id);

CREATE INDEX ix_groups_classroom_id ON groups (classroom_id);

CREATE TABLE document_revisions (
    id VARCHAR(36) NOT NULL, 
    group_id VARCHAR(36) NOT NULL, 
    revision INTEGER NOT NULL, 
    content TEXT NOT NULL, 
    language VARCHAR(12) NOT NULL, 
    author_id VARCHAR(36) NOT NULL, 
    created_at BIGINT NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(author_id) REFERENCES users (id), 
    FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
    CONSTRAINT uq_group_revision UNIQUE (group_id, revision)
);

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
    FOREIGN KEY(group_id) REFERENCES groups (id), 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX ix_events_classroom_id ON events (classroom_id);

CREATE INDEX ix_events_created_at ON events (created_at);

CREATE INDEX ix_events_user_id ON events (user_id);

CREATE TABLE group_comments (
    id VARCHAR(36) NOT NULL, 
    group_id VARCHAR(36) NOT NULL, 
    author_id VARCHAR(36) NOT NULL, 
    body TEXT NOT NULL, 
    created_at BIGINT NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(author_id) REFERENCES users (id), 
    FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE
);

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
);

CREATE TABLE group_members (
    group_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (group_id, user_id), 
    FOREIGN KEY(group_id) REFERENCES groups (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

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
    CONSTRAINT submission_status CHECK (status IN ('submitted','reviewed','revision_requested')), 
    CONSTRAINT submission_score CHECK (score IS NULL OR score >= 0), 
    FOREIGN KEY(activity_item_id) REFERENCES activity_items (id), 
    FOREIGN KEY(graded_by) REFERENCES users (id), 
    FOREIGN KEY(group_id) REFERENCES groups (id), 
    FOREIGN KEY(user_id) REFERENCES users (id), 
    CONSTRAINT uq_submission_attempt UNIQUE (activity_item_id, owner_key, attempt), 
    CONSTRAINT uq_submission_idempotency UNIQUE (user_id, client_id)
);

CREATE INDEX ix_submissions_activity_item_id ON submissions (activity_item_id);

CREATE INDEX ix_submissions_group_id ON submissions (group_id);

CREATE INDEX ix_submissions_user_id ON submissions (user_id);

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
);

CREATE INDEX ix_grade_revisions_submission_id ON grade_revisions (submission_id);

CREATE TABLE submission_files (
    submission_id VARCHAR(36) NOT NULL, 
    file_id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (submission_id, file_id), 
    FOREIGN KEY(file_id) REFERENCES stored_files (id), 
    FOREIGN KEY(submission_id) REFERENCES submissions (id) ON DELETE CASCADE
);

CREATE TABLE submission_members (
    submission_id VARCHAR(36) NOT NULL, 
    user_id VARCHAR(36) NOT NULL, 
    PRIMARY KEY (submission_id, user_id), 
    FOREIGN KEY(submission_id) REFERENCES submissions (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id)
);

INSERT INTO alembic_version (version_num) VALUES ('bb2030abeaf7') RETURNING alembic_version.version_num;

COMMIT;

