"""V2 independent training and bounded integration records. No private data in events."""
from __future__ import annotations
from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .models import Base, uid, now_ms


class SubjectMembership(Base):
    __tablename__ = 'subject_memberships'
    subject_id: Mapped[str] = mapped_column(ForeignKey('subjects.id'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    source: Mapped[str] = mapped_column(String(30), default='admin')


class TrainingCircle(Base):
    __tablename__ = 'training_circles'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    subject_id: Mapped[str] = mapped_column(ForeignKey('subjects.id'), default='informatics')
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[dict] = mapped_column(JSON)
    description: Mapped[dict] = mapped_column(JSON, default=dict)
    discoverable: Mapped[bool] = mapped_column(Boolean, default=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)


class CircleMember(Base):
    __tablename__ = 'circle_members'
    circle_id: Mapped[str] = mapped_column(ForeignKey('training_circles.id', ondelete='CASCADE'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    role: Mapped[str] = mapped_column(String(15), default='member')
    status: Mapped[str] = mapped_column(String(15), default='pending')
    transfer_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (CheckConstraint("role IN ('member','facilitator')", name='circle_role'), CheckConstraint("status IN ('pending','active')", name='circle_member_status'), Index('ix_circle_member_user', 'user_id', 'status'))


class TrainingCycle(Base):
    __tablename__ = 'training_cycles'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    circle_id: Mapped[str | None] = mapped_column(ForeignKey('training_circles.id'), nullable=True, index=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    title: Mapped[dict] = mapped_column(JSON)
    guidance: Mapped[dict] = mapped_column(JSON, default=dict)
    links: Mapped[list] = mapped_column(JSON, default=list)
    starts_at: Mapped[int] = mapped_column(BigInteger)
    ends_at: Mapped[int] = mapped_column(BigInteger)
    practice_starts_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    practice_ends_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    discussion_opens_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default='individual')
    status: Mapped[str] = mapped_column(String(15), default='draft')
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (
        CheckConstraint('(circle_id IS NULL AND owner_id IS NOT NULL) OR (circle_id IS NOT NULL AND owner_id IS NULL)', name='cycle_owner_xor'),
        CheckConstraint('ends_at > starts_at', name='cycle_time_order'),
        CheckConstraint("mode IN ('individual','collaborative')", name='cycle_mode'),
        CheckConstraint("status IN ('draft','published','cancelled')", name='cycle_status'),
        CheckConstraint('circle_id IS NULL OR (practice_starts_at IS NOT NULL AND practice_ends_at IS NOT NULL AND discussion_opens_at IS NOT NULL AND practice_ends_at > practice_starts_at)', name='circle_practice_times'),
        CheckConstraint("circle_id IS NULL OR mode != 'individual' OR discussion_opens_at >= practice_ends_at", name='individual_discussion_gate'),
    )


class TrainingPlan(Base):
    __tablename__ = 'training_plans'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    cycle_id: Mapped[str] = mapped_column(ForeignKey('training_cycles.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    goal: Mapped[dict] = mapped_column(JSON, default=dict)
    review: Mapped[dict] = mapped_column(JSON, default=dict)
    next_step: Mapped[dict] = mapped_column(JSON, default=dict)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (UniqueConstraint('cycle_id', 'user_id', name='uq_training_plan_owner'),)


class TrainingItem(Base):
    __tablename__ = 'training_items'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    plan_id: Mapped[str] = mapped_column(ForeignKey('training_plans.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(2000))
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    problem_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='not_started')
    position: Mapped[int] = mapped_column(Integer, default=0)
    carried_from_id: Mapped[str | None] = mapped_column(ForeignKey('training_items.id', ondelete='SET NULL'), nullable=True)
    client_id: Mapped[str] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (UniqueConstraint('plan_id', 'client_id', name='uq_training_item_mutation'), CheckConstraint("status IN ('not_started','attempted','revisit','completed')", name='training_item_status'))


class PracticeEntry(Base):
    __tablename__ = 'practice_entries'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    item_id: Mapped[str] = mapped_column(ForeignKey('training_items.id', ondelete='CASCADE'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    outcome: Mapped[str] = mapped_column(String(20))
    assistance: Mapped[str] = mapped_column(String(20), default='independent')
    reflection: Mapped[dict] = mapped_column(JSON, default=dict)
    next_step: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    client_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint('author_id', 'client_id', name='uq_practice_entry_mutation'), CheckConstraint("outcome IN ('not_started','attempted','revisit','completed')", name='entry_outcome'), CheckConstraint("assistance IN ('independent','hints','editorial','peer')", name='entry_assistance'))


class PeerPost(Base):
    __tablename__ = 'peer_posts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    cycle_id: Mapped[str] = mapped_column(ForeignKey('training_cycles.id'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(20), default='explanation')
    body: Mapped[dict] = mapped_column(JSON)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    client_id: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (UniqueConstraint('author_id', 'client_id', name='uq_peer_post_mutation'), CheckConstraint("kind IN ('help','explanation','logistics')", name='peer_post_kind'), Index('ix_peer_posts_cursor', 'cycle_id', 'created_at', 'id'))


class ModerationReport(Base):
    __tablename__ = 'moderation_reports'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reporter_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    circle_id: Mapped[str] = mapped_column(ForeignKey('training_circles.id'))
    post_id: Mapped[str | None] = mapped_column(ForeignKey('peer_posts.id'), nullable=True)
    reason: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(String(1000), default='')
    status: Mapped[str] = mapped_column(String(15), default='open')
    resolution: Mapped[str] = mapped_column(String(1000), default='')
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    resolved_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (CheckConstraint("status IN ('open','resolved')", name='report_status'),)


class ExternalAccount(Base):
    __tablename__ = 'external_accounts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    provider: Mapped[str] = mapped_column(String(20), default='codeforces')
    handle: Mapped[str] = mapped_column(String(24))
    normalized_handle: Mapped[str] = mapped_column(String(24), index=True)
    consent_at: Mapped[int] = mapped_column(BigInteger)
    leaderboard_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_status: Mapped[str] = mapped_column(String(24), default='pending_validation')
    # Nullable UNIQUE provides portable one-approved-link-per-school-handle enforcement.
    approved_handle_key: Mapped[str | None] = mapped_column(String(24), nullable=True, unique=True)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    approved_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    approval_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_attempt_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_success_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    next_refresh_at: Mapped[int] = mapped_column(BigInteger, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (UniqueConstraint('user_id', 'provider', name='uq_external_account_owner'), CheckConstraint("approval_status IN ('pending_validation','invalid_handle','pending_approval','approved','rejected','revoked','conflicted')", name='external_approval_state'), CheckConstraint("(approval_status = 'approved' AND approved_handle_key IS NOT NULL) OR (approval_status != 'approved' AND approved_handle_key IS NULL)", name='approved_handle_consistency'))


class CodeforcesProfile(Base):
    __tablename__ = 'codeforces_profile_cache'
    account_id: Mapped[str] = mapped_column(ForeignKey('external_accounts.id', ondelete='CASCADE'), primary_key=True)
    handle: Mapped[str] = mapped_column(String(24))
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank: Mapped[str | None] = mapped_column(String(80), nullable=True)
    registration_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_rank: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fetched_at: Mapped[int] = mapped_column(BigInteger)


class CodeforcesContestCache(Base):
    __tablename__ = 'codeforces_contest_cache'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    contests: Mapped[list] = mapped_column(JSON, default=list)
    fetched_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    next_refresh_at: Mapped[int] = mapped_column(BigInteger, default=0)
    last_error: Mapped[str | None] = mapped_column(String(40), nullable=True)
    __table_args__ = (CheckConstraint('id = 1', name='singleton_contest_cache'),)


class ExternalObservation(Base):
    __tablename__ = 'external_observations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    account_id: Mapped[str] = mapped_column(ForeignKey('external_accounts.id', ondelete='CASCADE'), index=True)
    submission_id: Mapped[int] = mapped_column(BigInteger)
    problem_key: Mapped[str] = mapped_column(String(80))
    verdict: Mapped[str] = mapped_column(String(40))
    external_at: Mapped[int] = mapped_column(BigInteger)
    observed_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    __table_args__ = (UniqueConstraint('account_id', 'submission_id', name='uq_external_observation'),)


class OperationLease(Base):
    __tablename__ = 'operation_leases'
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    not_before: Mapped[int] = mapped_column(BigInteger, default=0)
    expires_at: Mapped[int] = mapped_column(BigInteger, default=0)
    owner: Mapped[str] = mapped_column(String(36), default='')
    state: Mapped[dict] = mapped_column(JSON, default=dict)


class StorageBudget(Base):
    __tablename__ = 'storage_budget'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    committed_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (CheckConstraint('id = 1 AND committed_bytes >= 0 AND reserved_bytes >= 0', name='valid_storage_budget'),)


class UploadIntent(Base):
    __tablename__ = 'upload_intents'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    client_id: Mapped[str] = mapped_column(String(36))
    target_kind: Mapped[str] = mapped_column(String(12))
    target_id: Mapped[str] = mapped_column(String(36))
    classroom_id: Mapped[str] = mapped_column(ForeignKey('classrooms.id'))
    object_key: Mapped[str] = mapped_column(String(150))
    backend: Mapped[str] = mapped_column(String(15), default='local')
    reserved_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(80))
    filename: Mapped[str] = mapped_column(String(180))
    state: Mapped[str] = mapped_column(String(15), default='reserved')
    created_at: Mapped[int] = mapped_column(BigInteger, default=now_ms)
    expires_at: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (UniqueConstraint('owner_id', 'client_id', name='uq_upload_intent_client'), CheckConstraint("state IN ('reserved','uploading','ready','failed','deleting','cleaned')", name='upload_intent_state'), Index('ix_upload_intent_expiry', 'state', 'expires_at'))
