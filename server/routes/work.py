from __future__ import annotations
import hashlib
import json
import math
from fastapi import APIRouter
from sqlalchemy import func, select, update
from ..errors import DomainError, require
from ..models import Activity, ActivityItem, Classroom, Membership, Draft, GradeRevision, Group, GroupDocument, GroupMember, StoredFile, Submission, SubmissionFile, SubmissionMember, User, now_ms
from ..schemas import GradeInput, SubmissionInput, WorkInput
from ..security import Actor, Db
from ..services.access import classroom_access, classroom_ids, group_access, item_access, lock_open_activity, staff, submission_access
from ..services.events import audit, emit, notify
from ..services.serialize import columns, file_data, submission_data

router = APIRouter(prefix='/api', tags=['Drafts, submissions and grading'])


def validate_language(item: ActivityItem, language: str) -> None:
    require((item.snapshot['format'] == 'code' and language in ('python', 'cpp')) or (item.snapshot['format'] == 'written' and language == 'written'), 'invalid_language', 422)


@router.get('/drafts/{item_id}')
def get_draft(item_id: str, db: Db, user: Actor):
    item, activity = item_access(db, user, item_id)
    require(user.role == 'student')
    draft = db.get(Draft, (item_id, user.id))
    result = columns(draft, 'content', 'language', 'revision', 'updated_at') if draft else {'content': '', 'language': 'python' if item.snapshot['format'] == 'code' else 'written', 'revision': 0, 'updated_at': None}
    result['files'] = [file_data(f) for f in db.scalars(select(StoredFile).where(StoredFile.target_kind == 'draft', StoredFile.target_id == item_id, StoredFile.owner_id == user.id))]
    return result


@router.put('/drafts/{item_id}')
def save_draft(item_id: str, body: WorkInput, db: Db, user: Actor):
    item, activity = item_access(db, user, item_id, submitting=True)
    lock_open_activity(db, activity)
    validate_language(item, body.language)
    draft = db.get(Draft, (item_id, user.id))
    if draft is None:
        require(body.revision == 0, 'conflict', 409)
        draft = Draft(activity_item_id=item_id, user_id=user.id, content=body.content, language=body.language, revision=1, updated_at=now_ms())
        db.add(draft)
        db.flush()
    else:
        result = db.execute(update(Draft).where(Draft.activity_item_id == item_id, Draft.user_id == user.id, Draft.revision == body.revision).values(content=body.content, language=body.language, revision=Draft.revision + 1, updated_at=now_ms()))
        if result.rowcount != 1:
            db.refresh(draft)
            raise DomainError('conflict', 409, columns(draft, 'content', 'language', 'revision', 'updated_at'))
        db.refresh(draft)
    return columns(draft, 'content', 'language', 'revision', 'updated_at')


@router.post('/submissions', status_code=201)
def submit(body: SubmissionInput, db: Db, user: Actor):
    request_hash = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    existing = db.scalar(select(Submission).where(Submission.user_id == user.id, Submission.client_id == body.client_id))
    if existing:
        submission_access(db, user, existing.id)
        require(existing.request_hash == request_hash, 'idempotency_mismatch', 409)
        return submission_data(db, user, existing, detail=True)
    item, activity = item_access(db, user, body.activity_item_id, submitting=True)
    lock_open_activity(db, activity)
    db.execute(update(Classroom).where(Classroom.id == activity.classroom_id).values(active=Classroom.active))
    # Recheck membership after acquiring the offboarding/submit serialization lock.
    require(db.get(Membership, (activity.classroom_id, user.id), populate_existing=True) is not None, 'not_found', 404)
    content, language = body.content, body.language
    members = [user.id]
    owner_key = 'user:' + user.id
    if body.group_id:
        require(activity.kind != 'competition', 'competition_locked', 403)
        group = group_access(db, user, body.group_id, write=True)
        require(group.activity_item_id == item.id, 'invalid_group', 422)
        require(db.get(GroupMember, (group.id, user.id)) is not None)
        document = db.get(GroupDocument, group.id)
        require(body.group_revision == document.revision, 'conflict', 409)
        content, language = document.content, document.language
        eligible = select(User.id).join(GroupMember, GroupMember.user_id == User.id).join(Membership, (Membership.user_id == User.id) & (Membership.classroom_id == activity.classroom_id)).where(GroupMember.group_id == group.id, User.active.is_(True), User.role == 'student').order_by(User.id)
        # Lock eligible accounts as well, serializing account disable with authorship.
        members = list(db.scalars(eligible.with_for_update(of=User)))
        owner_key = 'group:' + group.id
    validate_language(item, language)
    require(bool(content.strip()) or bool(body.file_ids), 'empty_submission', 422)
    require(len(set(body.file_ids)) == len(body.file_ids), 'invalid_file', 422)
    for file_id in body.file_ids:
        file = db.get(StoredFile, file_id)
        require(file is not None, 'invalid_file', 422)
        if body.group_id:
            require(file.target_kind == 'group' and file.target_id == body.group_id, 'invalid_file', 422)
        else:
            require(file.target_kind == 'draft' and file.target_id == item.id and file.owner_id == user.id, 'invalid_file', 422)
    attempt = (db.scalar(select(func.max(Submission.attempt)).where(Submission.activity_item_id == item.id, Submission.owner_key == owner_key)) or 0) + 1
    require(attempt <= 100, 'attempt_limit', 409)
    submission = Submission(activity_item_id=item.id, user_id=user.id, group_id=body.group_id, owner_key=owner_key, client_id=body.client_id,
        request_hash=request_hash, attempt=attempt, content=content, language=language, group_revision=body.group_revision if body.group_id else None)
    db.add(submission)
    db.flush()
    for member in members:
        db.add(SubmissionMember(submission_id=submission.id, user_id=member))
    for file_id in body.file_ids:
        db.add(SubmissionFile(submission_id=submission.id, file_id=file_id))
    emit(db, 'submission', submission.id, classroom_id=activity.classroom_id, user_id=user.id, group_id=body.group_id)
    audit(db, user.id, 'submission.created', submission.id)
    db.flush()
    return submission_data(db, user, submission, detail=True)


@router.get('/reviews/queue')
def review_queue(db: Db, user: Actor, status: str = 'submitted',
                 classroom_id: str | None = None, cursor: str | None = None, limit: int = 30):
    """Staff-only bounded review list; stable (created_at,id) keyset pagination."""
    require(staff(user), 'forbidden', 403)
    require(status in ('submitted', 'reviewed', 'revision_requested', 'all'), 'invalid_input', 422)
    require(1 <= limit <= 50, 'invalid_input', 422)
    ids = classroom_ids(db, user)
    if classroom_id:
        classroom_access(db, user, classroom_id, write=True)
        ids = [classroom_id]
    query = select(Submission).join(ActivityItem, ActivityItem.id == Submission.activity_item_id).join(
        Activity, Activity.id == ActivityItem.activity_id).where(Activity.classroom_id.in_(ids))
    if status != 'all':
        query = query.where(Submission.status == status)
    if cursor:
        try:
            timestamp, item_id = cursor.split(':', 1)
            when = int(timestamp)
            from uuid import UUID
            if when < 0 or str(UUID(item_id)) != item_id:
                raise ValueError()
        except (ValueError, TypeError):
            raise DomainError('invalid_cursor', 422)
        from sqlalchemy import and_, or_
        query = query.where(or_(Submission.created_at < when,
            and_(Submission.created_at == when, Submission.id < item_id)))
    items = list(db.scalars(query.order_by(Submission.created_at.desc(), Submission.id.desc()).limit(limit + 1)))
    more = len(items) > limit
    items = items[:limit]
    return {'items': [submission_data(db, user, item) for item in items],
            'next_cursor': f'{items[-1].created_at}:{items[-1].id}' if more and items else None}


@router.get('/submissions')
def submissions(db: Db, user: Actor, activity_id: str | None = None, classroom_id: str | None = None):
    ids = classroom_ids(db, user)
    if classroom_id:
        from ..services.access import classroom_access
        classroom_access(db, user, classroom_id)
        ids = [classroom_id]
    query = select(Submission).join(ActivityItem).join(Activity).where(Activity.classroom_id.in_(ids))
    if activity_id:
        from ..services.access import activity_access
        activity_access(db, user, activity_id)
        query = query.where(Activity.id == activity_id)
    if user.role == 'student':
        query = query.join(SubmissionMember, SubmissionMember.submission_id == Submission.id).where(SubmissionMember.user_id == user.id)
    return [submission_data(db, user, s) for s in db.scalars(query.order_by(Submission.created_at.desc()).limit(1000))]


@router.get('/submissions/by-client-id/{client_id}')
def submission_receipt(client_id: str, db: Db, user: Actor):
    submission = db.scalar(select(Submission).where(Submission.user_id == user.id, Submission.client_id == client_id))
    require(submission is not None, 'not_found', 404)
    # A minimal receipt remains available to its requester after a deadline/removal.
    # It never grants access to sealed grades, files or another user's submission.
    return {'id': submission.id, 'client_id': submission.client_id, 'created_at': submission.created_at, 'attempt': submission.attempt, 'accepted': True}


@router.get('/submissions/{submission_id}')
def submission_detail(submission_id: str, db: Db, user: Actor):
    submission, item, activity = submission_access(db, user, submission_id)
    data = submission_data(db, user, submission, detail=True)
    if staff(user):
        data['grade_history'] = [dict(columns(g, 'version', 'score', 'criterion_scores', 'feedback', 'status', 'released', 'created_at'), teacher_name=db.get(User, g.teacher_id).display_name) for g in db.scalars(select(GradeRevision).where(GradeRevision.submission_id == submission_id).order_by(GradeRevision.version.desc()))]
    return data


@router.put('/submissions/{submission_id}/grade')
def grade(submission_id: str, body: GradeInput, db: Db, user: Actor):
    submission, item, activity = submission_access(db, user, submission_id, write=True)
    if item.rubric:
        require(len(body.criterion_scores) == len(item.rubric), 'invalid_rubric_score', 422)
        require(all(score <= criterion['max'] for score, criterion in zip(body.criterion_scores, item.rubric)), 'invalid_rubric_score', 422)
        score = sum(body.criterion_scores)
        if body.score is not None:
            require(math.isclose(score, body.score, abs_tol=0.001), 'invalid_rubric_score', 422)
    else:
        require(body.score is not None and not body.criterion_scores, 'score_required', 422)
        score = body.score
    require(score <= item.points, 'score_out_of_range', 422)
    # A competition's global release gate remains authoritative regardless of this field.
    released = body.release if activity.kind != 'competition' else False
    result = db.execute(update(Submission).where(Submission.id == submission_id, Submission.grade_version == body.version).values(
        score=score, criterion_scores=body.criterion_scores, feedback=body.feedback, status=body.status, released=released,
        graded_by=user.id, graded_at=now_ms(), grade_version=Submission.grade_version + 1))
    require(result.rowcount == 1, 'conflict', 409)
    db.add(GradeRevision(submission_id=submission_id, teacher_id=user.id, version=body.version + 1, score=score, criterion_scores=body.criterion_scores, feedback=body.feedback, status=body.status, released=released))
    members = list(db.scalars(select(SubmissionMember.user_id).where(SubmissionMember.submission_id == submission_id)))
    if released or activity.results_published:
        notify(db, members, 'grade_released', item.snapshot['title'], '/submissions/' + submission_id)
    emit(db, 'submission', submission_id, classroom_id=activity.classroom_id, user_id=submission.user_id, group_id=submission.group_id)
    audit(db, user.id, 'submission.graded', submission_id)
    db.refresh(submission)
    return submission_data(db, user, submission, detail=True)
