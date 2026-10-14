"""Relational domain model. All instants are UTC Unix milliseconds, on both databases."""
from __future__ import annotations
import time
import uuid
from typing import Any
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid() -> str:
    return str(uuid.uuid4())


def now_ms() -> int:
    return time.time_ns() // 1_000_000


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(12), default='student')
    locale: Mapped[str] = mapped_column(String(2), default='ru')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (CheckConstraint("role IN ('admin','teacher','student')", name='valid_user_role'), CheckConstraint("locale IN ('ru','en')", name='valid_locale'))


class AuthSession(Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    expires_at: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Subject(Base):
    __tablename__ = 'subjects'
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[dict[str, str]] = mapped_column(JSON)


class Topic(Base):
    __tablename__ = 'topics'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey('subjects.id'), index=True)
    name: Mapped[dict[str, str]] = mapped_column(JSON)
    created_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)


class Classroom(Base):
    __tablename__ = 'classrooms'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey('subjects.id'), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[dict[str, str]] = mapped_column(JSON)
    description: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Membership(Base):
    __tablename__ = 'memberships'
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    joined_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Invitation(Base):
    __tablename__ = 'invitations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(12))
    classroom_id: Mapped[str | None] = mapped_column(ForeignKey('classrooms.id'), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[int] = mapped_column(BigInteger)
    accepted_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    __table_args__ = (CheckConstraint("role IN ('teacher','student')", name='valid_invite_role'),)


class EnrollmentInvitation(Base):
    """Single-use, email-bound existing-account classroom invitation."""
    __tablename__ = 'enrollment_invitations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'), nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    accepted_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class ClubSettings(Base):
    __tablename__ = 'club_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[dict[str, str]] = mapped_column(JSON)
    timezone: Mapped[str] = mapped_column(String(60), default='UTC')
    __table_args__ = (CheckConstraint('id = 1', name='singleton_settings'),)


class Announcement(Base):
    __tablename__ = 'announcements'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    body: Mapped[dict[str, str]] = mapped_column(JSON)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Resource(Base):
    __tablename__ = 'resources'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'), index=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey('topics.id'), nullable=True)
    title: Mapped[dict[str, str]] = mapped_column(JSON)
    body: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Problem(Base):
    __tablename__ = 'problems'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    topic_id: Mapped[str | None] = mapped_column(ForeignKey('topics.id'), nullable=True, index=True)
    title: Mapped[dict[str, str]] = mapped_column(JSON)
    statement: Mapped[dict[str, str]] = mapped_column(JSON)
    subtopic: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    hints: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    solution: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    examples: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    source: Mapped[str] = mapped_column(String(300), default='')
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    format: Mapped[str] = mapped_column(String(12), default='written')
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    search_text: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (CheckConstraint('difficulty BETWEEN 1 AND 5', name='problem_difficulty'), CheckConstraint("format IN ('written','code')", name='problem_format'))


class ProblemSet(Base):
    __tablename__ = 'problem_sets'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'), index=True)
    title: Mapped[dict[str, str]] = mapped_column(JSON)
    description: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class SetItem(Base):
    __tablename__ = 'set_items'
    set_id: Mapped[str] = mapped_column(ForeignKey('problem_sets.id', ondelete='CASCADE'), primary_key=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey('problems.id'), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)


class Activity(Base):
    """One rigorously enforced workflow for assignments, live sessions and competitions."""
    __tablename__ = 'activities'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'), index=True)
    kind: Mapped[str] = mapped_column(String(12), index=True)
    title: Mapped[dict[str, str]] = mapped_column(JSON)
    description: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    starts_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ends_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String(12), default='draft')
    results_published: Mapped[bool] = mapped_column(Boolean, default=False)
    edit_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    announcement: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (CheckConstraint("kind IN ('assignment','session','competition')", name='activity_kind'), CheckConstraint("status IN ('draft','published','live','ended')", name='activity_status'), CheckConstraint('ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at', name='activity_time_order'))


class ActivityItem(Base):
    __tablename__ = 'activity_items'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    activity_id: Mapped[str] = mapped_column(ForeignKey('activities.id', ondelete='CASCADE'), index=True)
    problem_id: Mapped[str] = mapped_column(ForeignKey('problems.id'), index=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    position: Mapped[int] = mapped_column(Integer)
    points: Mapped[float] = mapped_column(Float)
    rubric: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    released_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    hints_released: Mapped[bool] = mapped_column(Boolean, default=False)
    solution_released: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint('activity_id', 'problem_id', name='uq_activity_problem'), CheckConstraint('points > 0 AND points <= 1000', name='item_points'))


class Participant(Base):
    __tablename__ = 'participants'
    activity_id: Mapped[str] = mapped_column(ForeignKey('activities.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)


class HelpRequest(Base):
    __tablename__ = 'help_requests'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    activity_id: Mapped[str] = mapped_column(ForeignKey('activities.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(String(1000))
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Group(Base):
    __tablename__ = 'groups'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'), index=True)
    activity_item_id: Mapped[str] = mapped_column(ForeignKey('activity_items.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class GroupMember(Base):
    __tablename__ = 'group_members'
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)


class GroupDocument(Base):
    __tablename__ = 'group_documents'
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id', ondelete='CASCADE'), primary_key=True)
    content: Mapped[str] = mapped_column(Text, default='')
    language: Mapped[str] = mapped_column(String(12), default='written')
    revision: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)


class DocumentRevision(Base):
    __tablename__ = 'document_revisions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id', ondelete='CASCADE'), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(12))
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (UniqueConstraint('group_id', 'revision', name='uq_group_revision'),)


class GroupComment(Base):
    __tablename__ = 'group_comments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey('groups.id', ondelete='CASCADE'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Draft(Base):
    __tablename__ = 'drafts'
    activity_item_id: Mapped[str] = mapped_column(ForeignKey('activity_items.id'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    content: Mapped[str] = mapped_column(Text, default='')
    language: Mapped[str] = mapped_column(String(12), default='written')
    revision: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Submission(Base):
    __tablename__ = 'submissions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    activity_item_id: Mapped[str] = mapped_column(ForeignKey('activity_items.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey('groups.id'), nullable=True, index=True)
    owner_key: Mapped[str] = mapped_column(String(50))
    client_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    attempt: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(12))
    group_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    status: Mapped[str] = mapped_column(String(24), default='submitted')
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    criterion_scores: Mapped[list[float]] = mapped_column(JSON, default=list)
    feedback: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    released: Mapped[bool] = mapped_column(Boolean, default=False)
    graded_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    graded_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    grade_version: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (Index('ix_submission_review_queue', 'created_at', 'id'), UniqueConstraint('user_id', 'client_id', name='uq_submission_idempotency'), UniqueConstraint('activity_item_id', 'owner_key', 'attempt', name='uq_submission_attempt'), CheckConstraint("status IN ('submitted','reviewed','revision_requested')", name='submission_status'), CheckConstraint('score IS NULL OR score >= 0', name='submission_score'))


class SubmissionMember(Base):
    """Snapshot of submitters: a later team change cannot grant access to past work."""
    __tablename__ = 'submission_members'
    submission_id: Mapped[str] = mapped_column(ForeignKey('submissions.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)


class GradeRevision(Base):
    __tablename__ = 'grade_revisions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    submission_id: Mapped[str] = mapped_column(ForeignKey('submissions.id'), index=True)
    teacher_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    version: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    criterion_scores: Mapped[list[float]] = mapped_column(JSON)
    feedback: Mapped[dict[str, str]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(24))
    released: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class StoredFile(Base):
    __tablename__ = 'stored_files'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'), index=True)
    target_kind: Mapped[str] = mapped_column(String(12))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    filename: Mapped[str] = mapped_column(String(180))
    media_type: Mapped[str] = mapped_column(String(80))
    size: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    storage_backend: Mapped[str] = mapped_column(String(15), default='local', server_default='local')
    object_key: Mapped[str | None] = mapped_column(String(150), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __table_args__ = (CheckConstraint("target_kind IN ('problem','resource','draft','group')", name='file_target_kind'), CheckConstraint('size > 0 AND size <= 8388608', name='file_size'))


class SubmissionFile(Base):
    __tablename__ = 'submission_files'
    submission_id: Mapped[str] = mapped_column(ForeignKey('submissions.id', ondelete='CASCADE'), primary_key=True)
    file_id: Mapped[str] = mapped_column(ForeignKey('stored_files.id'), primary_key=True)


class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    link: Mapped[str] = mapped_column(String(200))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class Event(Base):
    """Durable, privacy-scoped invalidation events; never contains submitted work."""
    __tablename__ = 'events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classroom_id: Mapped[str | None] = mapped_column(ForeignKey('classrooms.id'), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey('groups.id'), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)


class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[dict] = mapped_column(JSON, default=dict, server_default='{}')
    entity_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms, index=True)


class RateLimit(Base):
    __tablename__ = 'rate_limits'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=1)

# Separate source module, same relational model and Alembic metadata.
from .models_v2 import (SubjectMembership, TrainingCircle, CircleMember, TrainingCycle, TrainingPlan,
    TrainingItem, PracticeEntry, PeerPost, ModerationReport, ExternalAccount, CodeforcesProfile,
    CodeforcesContestCache, ExternalObservation, OperationLease, StorageBudget, UploadIntent)
