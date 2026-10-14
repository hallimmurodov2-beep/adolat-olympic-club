"""Central authorization policy. IDs from the client never establish ownership."""
from __future__ import annotations
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session
from ..models import Activity, ActivityItem, Classroom, Group, GroupMember, Membership, Participant, Problem, Submission, SubmissionMember, User, now_ms
from ..errors import DomainError, require


def staff(user: User) -> bool:
    return user.role in ('admin', 'teacher')


def classroom_ids(db: Session, user: User) -> list[str]:
    query = select(Classroom.id)
    if user.role == 'teacher':
        query = query.where(Classroom.teacher_id == user.id)
    elif user.role == 'student':
        query = query.join(Membership, Membership.classroom_id == Classroom.id).where(Membership.user_id == user.id)
    return list(db.scalars(query))


def manages(user: User, classroom: Classroom) -> bool:
    return user.role == 'admin' or (user.role == 'teacher' and classroom.teacher_id == user.id)


def classroom_access(db: Session, user: User, classroom_id: str, write: bool = False) -> Classroom:
    room = db.get(Classroom, classroom_id)
    require(room is not None, 'not_found', 404)
    allowed = manages(user, room)
    if not write and user.role == 'student':
        allowed = db.get(Membership, (classroom_id, user.id)) is not None
    require(allowed, 'not_found', 404)
    return room


def phase(activity: Activity, instant: int | None = None) -> str:
    at = now_ms() if instant is None else instant
    if activity.status == 'draft':
        return 'draft'
    if activity.status == 'ended' or (activity.ends_at is not None and at >= activity.ends_at):
        return 'ended'
    if activity.starts_at is not None and at < activity.starts_at:
        return 'upcoming'
    if activity.kind == 'session' and activity.status != 'live':
        return 'upcoming'
    return 'active'


def activity_access(db: Session, user: User, activity_id: str, write: bool = False) -> Activity:
    activity = db.get(Activity, activity_id)
    require(activity is not None, 'not_found', 404)
    classroom_access(db, user, activity.classroom_id, write)
    if user.role == 'student':
        require(activity.status != 'draft', 'not_found', 404)
        if activity.kind == 'competition':
            require(db.get(Participant, (activity.id, user.id)) is not None, 'not_found', 404)
    return activity


def item_is_visible(activity: Activity, item: ActivityItem, at: int | None = None) -> bool:
    if activity.status == 'draft':
        return False
    if activity.kind == 'competition' and phase(activity, at) == 'upcoming':
        return False
    if activity.kind == 'session' and item.released_at is None:
        return False
    return True


def item_access(db: Session, user: User, item_id: str, submitting: bool = False) -> tuple[ActivityItem, Activity]:
    item = db.get(ActivityItem, item_id)
    require(item is not None, 'not_found', 404)
    activity = activity_access(db, user, item.activity_id)
    if user.role == 'student':
        require(item_is_visible(activity, item), 'not_found', 404)
    if submitting:
        require(user.role == 'student', 'forbidden', 403)
        require(phase(activity) == 'active', 'deadline_closed', 409)
        require(db.get(Classroom, activity.classroom_id).active, 'classroom_archived', 409)
    return item, activity


def competing(db: Session, user: User) -> bool:
    if user.role != 'student':
        return False
    at = now_ms()
    return bool(db.scalar(select(Activity.id).join(Participant, Participant.activity_id == Activity.id)
        .join(Membership, and_(Membership.classroom_id == Activity.classroom_id, Membership.user_id == user.id))
        .where(Participant.user_id == user.id, Activity.kind == 'competition', Activity.status == 'published', Activity.starts_at <= at, Activity.ends_at > at).limit(1)))


def released_material(db: Session, user: User, problem: Problem) -> tuple[bool, bool]:
    if staff(user):
        return True, True
    if competing(db, user):
        return False, False
    hints, solution = False, False
    for item, activity in db.execute(select(ActivityItem, Activity).join(Activity, Activity.id == ActivityItem.activity_id).where(ActivityItem.problem_id == problem.id)):
        # Reuse never grants access outside the enrolled classroom or competition roster.
        if not db.get(Membership, (activity.classroom_id, user.id)):
            continue
        if activity.kind == 'competition' and (not db.get(Participant, (activity.id, user.id)) or not activity.results_published or phase(activity) != 'ended'):
            continue
        if item_is_visible(activity, item):
            hints = hints or item.hints_released
            solution = solution or item.solution_released
    return hints, solution


def problem_access(db: Session, user: User, problem_id: str, write: bool = False) -> Problem:
    problem = db.get(Problem, problem_id)
    require(problem is not None, 'not_found', 404)
    classroom_access(db, user, problem.classroom_id, write)
    if user.role == 'student' and not problem.published:
        allowed = False
        for item, activity in db.execute(select(ActivityItem, Activity).join(Activity, Activity.id == ActivityItem.activity_id).where(ActivityItem.problem_id == problem.id)):
            if activity.kind == 'competition' and not db.get(Participant, (activity.id, user.id)):
                continue
            if item_is_visible(activity, item):
                allowed = True
                break
        require(allowed, 'not_found', 404)
    return problem


def group_access(db: Session, user: User, group_id: str, write: bool = False) -> Group:
    require(not competing(db, user), 'competition_locked', 403)
    group = db.get(Group, group_id)
    require(group is not None, 'not_found', 404)
    room = classroom_access(db, user, group.classroom_id)
    member = db.get(GroupMember, (group.id, user.id)) is not None
    require(manages(user, room) or member or (group.shared and not write), 'not_found', 404)
    if user.role == 'student':
        item_access(db, user, group.activity_item_id, submitting=write)
    return group


def submission_access(db: Session, user: User, submission_id: str, write: bool = False) -> tuple[Submission, ActivityItem, Activity]:
    submission = db.get(Submission, submission_id)
    require(submission is not None, 'not_found', 404)
    item = db.get(ActivityItem, submission.activity_item_id)
    activity = db.get(Activity, item.activity_id)
    room = classroom_access(db, user, activity.classroom_id, write)
    if not manages(user, room):
        require(db.get(SubmissionMember, (submission.id, user.id)) is not None, 'not_found', 404)
    return submission, item, activity


def grade_visible(user: User, submission: Submission, activity: Activity) -> bool:
    if staff(user):
        return True
    if activity.kind == 'competition':
        return activity.results_published and phase(activity) == 'ended' and submission.status != 'submitted'
    return submission.released


def lock_open_activity(db: Session, activity: Activity) -> None:
    """A conditional write serializes deadline/end races, including on SQLite.

    The server's acceptance time is the instant of this check, not a browser value.
    The transaction keeps the activity row locked until the new work is committed.
    """
    from sqlalchemy import update
    at = now_ms()
    valid_status = 'live' if activity.kind == 'session' else 'published'
    query = update(Activity).where(Activity.id == activity.id, Activity.status == valid_status,
        or_(Activity.starts_at.is_(None), Activity.starts_at <= at),
        or_(Activity.ends_at.is_(None), Activity.ends_at > at)).values(status=Activity.status)
    result = db.execute(query.execution_options(synchronize_session=False))
    require(result.rowcount == 1, 'deadline_closed', 409)
