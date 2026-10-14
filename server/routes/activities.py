from __future__ import annotations
from fastapi import APIRouter, Query
from sqlalchemy import delete, func, or_, select, update
from ..errors import require
from ..models import Activity, ActivityItem, Classroom, HelpRequest, Membership, Participant, Problem, Submission, SubmissionMember, StoredFile, User, now_ms
from ..schemas import ActivityInput, ActivityDraftEdit, InterruptionExtension, ControlInput, HelpInput, ReleaseInput
from ..security import Actor, Db
from ..services.access import activity_access, classroom_access, classroom_ids, item_is_visible, phase, problem_access, staff
from ..services.events import audit, class_students, emit, notify
from ..services.serialize import activity_data, columns, item_data, problem_snapshot, submission_data

router = APIRouter(prefix='/api', tags=['Assignments, live sessions and competitions'])


@router.get('/activities')
def activities(db: Db, user: Actor, kind: str | None = None, classroom_id: str | None = None):
    ids = classroom_ids(db, user)
    if classroom_id:
        classroom_access(db, user, classroom_id)
        ids = [classroom_id]
    query = select(Activity).where(Activity.classroom_id.in_(ids))
    if kind:
        require(kind in ('assignment', 'session', 'competition'), 'invalid_input', 422)
        query = query.where(Activity.kind == kind)
    if user.role == 'student':
        query = query.where(Activity.status != 'draft', or_(Activity.kind != 'competition', Activity.id.in_(select(Participant.activity_id).where(Participant.user_id == user.id))))
    return [activity_data(db, a) for a in db.scalars(query.order_by(Activity.created_at.desc()).limit(300))]


@router.post('/activities', status_code=201)
def create_activity(body: ActivityInput, db: Db, user: Actor):
    room = classroom_access(db, user, body.classroom_id, write=True)
    require(room.active, 'classroom_archived', 409)
    problems = []
    for item in body.items:
        problem = problem_access(db, user, item.problem_id, write=True)
        require(problem.classroom_id == room.id, 'invalid_problem', 422)
        problems.append(problem)
    students = class_students(db, room.id)
    eligible = body.eligible_ids if body.eligible_ids is not None else students
    require(set(eligible).issubset(students), 'invalid_student', 422)
    if body.kind == 'competition':
        require(len(eligible) > 0, 'no_participants', 422)
    activity = Activity(**body.model_dump(exclude={'items', 'eligible_ids'}))
    db.add(activity)
    db.flush()
    for position, (item, problem) in enumerate(zip(body.items, problems)):
        db.add(ActivityItem(activity_id=activity.id, problem_id=problem.id, snapshot=dict(problem_snapshot(problem), file_ids=list(db.scalars(select(StoredFile.id).where(StoredFile.target_kind == 'problem', StoredFile.target_id == problem.id)))), position=position, points=item.points, rubric=[c.model_dump() for c in item.rubric]))
    if activity.kind == 'competition':
        for user_id in set(eligible):
            db.add(Participant(activity_id=activity.id, user_id=user_id))
    audit(db, user.id, 'activity.created', activity.id)
    emit(db, 'activity', activity.id, classroom_id=room.id)
    return activity_data(db, activity)


@router.post('/activities/{activity_id}/clone', status_code=201)
def clone_activity(activity_id: str, db: Db, user: Actor):
    source = activity_access(db, user, activity_id, write=True)
    room = db.scalar(select(Classroom).where(Classroom.id == source.classroom_id).with_for_update())
    require(room is not None and room.active, 'classroom_archived', 409)
    # Competition eligibility and live-session locks must never be copied implicitly.
    require(source.kind in ('assignment', 'session'), 'invalid_transition', 409)
    clone = Activity(classroom_id=source.classroom_id, kind=source.kind,
        title=dict(source.title), description=dict(source.description),
        starts_at=None, ends_at=None, duration_minutes=source.duration_minutes,
        status='draft', results_published=False)
    db.add(clone)
    db.flush()
    for item in db.scalars(select(ActivityItem).where(ActivityItem.activity_id == source.id).order_by(ActivityItem.position)):
        # Preserve creation-time content snapshot and attachment ids; no grades/work/people.
        db.add(ActivityItem(activity_id=clone.id, problem_id=item.problem_id,
            snapshot=dict(item.snapshot), position=item.position, points=item.points,
            rubric=list(item.rubric), released_at=None, hints_released=False, solution_released=False))
    audit(db, user.id, 'activity.cloned', clone.id)
    emit(db, 'activity', clone.id, classroom_id=clone.classroom_id)
    return activity_data(db, clone)


@router.patch('/activities/{activity_id}/draft')
def edit_draft(activity_id: str, body: ActivityDraftEdit, db: Db, user: Actor):
    activity = activity_access(db, user, activity_id, write=True)
    room = db.get(Classroom, activity.classroom_id)
    require(room is not None and room.active, 'classroom_archived', 409)
    require(activity.status == 'draft', 'activity_immutable', 409)
    require(activity.kind != 'competition' or (body.starts_at is not None and body.ends_at is not None), 'invalid_input', 422)
    result = db.execute(update(Activity).where(Activity.id == activity_id,
        Activity.status == 'draft', Activity.edit_version == body.edit_version).values(
        title=body.title, description=body.description, starts_at=body.starts_at,
        ends_at=body.ends_at, duration_minutes=body.duration_minutes,
        edit_version=Activity.edit_version + 1))
    require(result.rowcount == 1, 'conflict', 409)
    db.refresh(activity)
    audit(db, user.id, 'activity.draft_edited', activity.id)
    emit(db, 'activity', activity.id, classroom_id=activity.classroom_id)
    return activity_data(db, activity)


@router.get('/activities/{activity_id}/preflight')
def activity_preflight(activity_id: str, db: Db, user: Actor):
    """Explicit classroom-scoped readiness facts; not a promise of provider uptime."""
    activity = activity_access(db, user, activity_id, write=True)
    require(activity.kind in ('competition', 'session'), 'invalid_transition', 409)
    room = db.get(Classroom, activity.classroom_id)
    item_count = db.scalar(select(func.count(ActivityItem.id)).where(ActivityItem.activity_id == activity_id)) or 0
    eligible = (db.scalar(select(func.count(Participant.user_id)).where(Participant.activity_id == activity_id)) or 0
                if activity.kind == 'competition' else len(class_students(db, activity.classroom_id)))
    accepted = (db.scalar(select(func.count(Submission.id)).join(ActivityItem).where(ActivityItem.activity_id == activity_id)) or 0)
    timestamp = now_ms()
    return {'server_now': timestamp, 'activity_id': activity.id, 'kind': activity.kind,
        'status': activity.status, 'starts_at': activity.starts_at, 'ends_at': activity.ends_at,
        'item_count': item_count, 'eligible_participant_count': eligible,
        'recorded_submission_count': accepted, 'classroom_active': bool(room and room.active),
        'checks': {'has_items': item_count > 0, 'has_eligible_participants': eligible > 0,
            'future_deadline': activity.ends_at is not None and activity.ends_at > timestamp,
            'results_sealed': not activity.results_published},
        'warning': 'This is an application readiness snapshot, not a connectivity/backup guarantee.'}


@router.post('/activities/{activity_id}/interruption-extension')
def exceptional_extension(activity_id: str, body: InterruptionExtension, db: Db, user: Actor):
    """Only a school admin may extend a still-open timed activity by <= 2h.

    No automatic post-deadline extension/reopening, or client-clock-based acceptance.
    The school must decide fairness and document the reason independently.
    """
    require(user.role == 'admin', 'forbidden', 403)
    activity = activity_access(db, user, activity_id, write=True)
    require(activity.kind in ('competition', 'session'), 'invalid_transition', 409)
    require(activity.status == ('live' if activity.kind == 'session' else 'published'), 'invalid_transition', 409)
    now = now_ms()
    require(body.expected_ends_at > now, 'deadline_closed', 409)
    require(body.new_ends_at > body.expected_ends_at, 'invalid_input', 422)
    require(body.new_ends_at - body.expected_ends_at <= 2 * 60 * 60 * 1000, 'invalid_input', 422)
    previous = body.expected_ends_at
    changed = db.execute(update(Activity).where(Activity.id == activity_id,
        Activity.ends_at == previous, Activity.ends_at > now, Activity.status == activity.status,
        Activity.results_published.is_(False)).values(ends_at=body.new_ends_at, edit_version=Activity.edit_version + 1))
    require(changed.rowcount == 1, 'conflict', 409)
    audit(db, user.id, 'activity.interruption_extension', activity.id,
        {'old_ends_at': previous, 'new_ends_at': body.new_ends_at, 'reason': body.reason})
    recipients = (list(db.scalars(select(Participant.user_id).where(Participant.activity_id == activity_id)))
        if activity.kind == 'competition' else class_students(db, activity.classroom_id))
    notify(db, recipients, 'activity_window_extended', activity.title, '/activities/' + activity.id)
    emit(db, 'activity', activity.id, classroom_id=activity.classroom_id)
    db.refresh(activity)
    return activity_data(db, activity)


@router.get('/activities/{activity_id}')
def activity_detail(activity_id: str, db: Db, user: Actor):
    activity = activity_access(db, user, activity_id)
    result = activity_data(db, activity)
    result['server_now'] = now_ms()
    result['items'] = [item_data(db, user, item, activity) for item in db.scalars(select(ActivityItem).where(ActivityItem.activity_id == activity_id).order_by(ActivityItem.position)) if staff(user) or item_is_visible(activity, item)]
    submissions = select(Submission).join(ActivityItem).where(ActivityItem.activity_id == activity_id).order_by(Submission.created_at.desc())
    if user.role == 'student':
        submissions = submissions.join(SubmissionMember, SubmissionMember.submission_id == Submission.id).where(SubmissionMember.user_id == user.id)
    result['submissions'] = [submission_data(db, user, s) for s in db.scalars(submissions.limit(1000))]
    requests = select(HelpRequest).where(HelpRequest.activity_id == activity_id).order_by(HelpRequest.created_at.desc())
    if user.role == 'student':
        requests = requests.where(HelpRequest.user_id == user.id)
    result['help_requests'] = [dict(columns(h, 'id', 'body', 'resolved', 'created_at', 'user_id'), author_name=db.get(User, h.user_id).display_name) for h in db.scalars(requests.limit(150))]
    result['participant_count'] = db.scalar(select(func.count()).select_from(Participant).where(Participant.activity_id == activity_id)) if activity.kind == 'competition' else len(class_students(db, activity.classroom_id))
    if staff(user):
        eligible_ids = list(db.scalars(select(Participant.user_id).where(Participant.activity_id == activity_id))) if activity.kind == 'competition' else class_students(db, activity.classroom_id)
        result['participants'] = [columns(u, 'id', 'display_name') for u in db.scalars(select(User).where(User.id.in_(eligible_ids)))]
    return result


@router.delete('/activities/{activity_id}')
def delete_draft(activity_id: str, db: Db, user: Actor):
    activity = activity_access(db, user, activity_id, write=True)
    require(activity.status == 'draft', 'activity_immutable', 409)
    # Foreign keys deliberately reject deletion when a group already references an item.
    from ..models import Group
    has_groups = db.scalar(select(Group.id).join(ActivityItem, ActivityItem.id == Group.activity_item_id).where(ActivityItem.activity_id == activity_id).limit(1))
    require(has_groups is None, 'activity_in_use', 409)
    audit(db, user.id, 'activity.deleted', activity.id)
    emit(db, 'activity', activity.id, classroom_id=activity.classroom_id)
    db.delete(activity)
    return {'ok': True}


@router.post('/activities/{activity_id}/control')
def control(activity_id: str, body: ControlInput, db: Db, user: Actor):
    activity = activity_access(db, user, activity_id, write=True)
    db.execute(update(Activity).where(Activity.id == activity_id).values(status=Activity.status).execution_options(synchronize_session=False))
    db.refresh(activity)
    recipients = list(db.scalars(select(Participant.user_id).where(Participant.activity_id == activity_id))) if activity.kind == 'competition' else class_students(db, activity.classroom_id)
    if body.action == 'publish':
        require(activity.kind in ('assignment', 'competition') and activity.status == 'draft', 'invalid_transition', 409)
        require(activity.ends_at is None or activity.ends_at > now_ms(), 'deadline_closed', 409)
        activity.status = 'published'
        notify(db, recipients, 'activity_published', activity.title, '/activities/' + activity.id)
    elif body.action == 'start':
        require(activity.kind == 'session' and activity.status == 'draft', 'invalid_transition', 409)
        activity.status = 'live'
        activity.starts_at = now_ms()
        activity.ends_at = activity.starts_at + activity.duration_minutes * 60000
        notify(db, recipients, 'session_started', activity.title, '/activities/' + activity.id)
    elif body.action == 'end':
        require(activity.status not in ('draft', 'ended'), 'invalid_transition', 409)
        activity.status = 'ended'
        # Preserve the planned window; status is also part of every acceptance check.
    elif body.action == 'publish_results':
        require(phase(activity) == 'ended', 'results_before_end', 409)
        ungraded = db.scalar(select(func.count()).select_from(Submission).join(ActivityItem).where(ActivityItem.activity_id == activity_id, Submission.status == 'submitted'))
        require(ungraded == 0, 'ungraded_work', 409)
        require(not activity.results_published, 'invalid_transition', 409)
        activity.results_published = True
        notify(db, recipients, 'results_published', activity.title, '/activities/' + activity.id)
    elif body.action == 'announce':
        require(bool(body.body), 'invalid_input', 422)
        activity.announcement = body.body
    audit(db, user.id, 'activity.' + body.action, activity.id)
    emit(db, 'activity', activity.id, classroom_id=activity.classroom_id)
    return activity_data(db, activity)


@router.post('/activities/{activity_id}/items/{item_id}/release')
def release_item(activity_id: str, item_id: str, body: ReleaseInput, db: Db, user: Actor):
    activity = activity_access(db, user, activity_id, write=True)
    item = db.get(ActivityItem, item_id)
    require(item is not None and item.activity_id == activity.id, 'not_found', 404)
    if body.action == 'problem':
        require(activity.kind == 'session' and phase(activity) == 'active', 'invalid_transition', 409)
        # A released statement cannot be pulled away from a student who is solving it.
        require(body.enabled, 'cannot_unrelease', 409)
        item.released_at = item.released_at or now_ms()
    else:
        require(item_is_visible(activity, item), 'invalid_transition', 409)
        if activity.kind == 'competition':
            require(phase(activity) == 'ended' and activity.results_published, 'competition_locked', 403)
        setattr(item, 'hints_released' if body.action == 'hints' else 'solution_released', body.enabled)
    audit(db, user.id, 'item.release.' + body.action, item.id)
    emit(db, 'activity', activity.id, classroom_id=activity.classroom_id)
    return item_data(db, user, item, activity)


@router.post('/activities/{activity_id}/help', status_code=201)
def request_help(activity_id: str, body: HelpInput, db: Db, user: Actor):
    activity = activity_access(db, user, activity_id)
    require(user.role == 'student' and activity.kind == 'session', 'forbidden', 403)
    require(phase(activity) == 'active', 'deadline_closed', 409)
    existing = db.scalar(select(HelpRequest).where(HelpRequest.activity_id == activity_id, HelpRequest.user_id == user.id, HelpRequest.resolved.is_(False)))
    if existing:
        return columns(existing, 'id', 'body', 'resolved', 'created_at')
    help_request = HelpRequest(activity_id=activity.id, user_id=user.id, body=body.body.strip())
    db.add(help_request)
    db.flush()
    emit(db, 'activity', activity.id, classroom_id=activity.classroom_id, user_id=user.id)
    return columns(help_request, 'id', 'body', 'resolved', 'created_at')


@router.post('/help/{help_id}/resolve')
def resolve_help(help_id: str, db: Db, user: Actor):
    help_request = db.get(HelpRequest, help_id)
    require(help_request is not None, 'not_found', 404)
    activity = activity_access(db, user, help_request.activity_id, write=True)
    help_request.resolved = True
    emit(db, 'activity', activity.id, classroom_id=activity.classroom_id, user_id=help_request.user_id)
    return {'ok': True}
