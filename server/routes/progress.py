from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from fastapi import APIRouter
from sqlalchemy import func, or_, select, update
from ..errors import require
from ..models import Activity, ActivityItem, Classroom, Membership, Notification, Participant, Submission, SubmissionMember, Topic, User, now_ms
from ..security import Actor, Db
from ..services.access import classroom_access, classroom_ids, competing, grade_visible, item_is_visible, phase, staff
from ..services.serialize import activity_data, columns, submission_data
from .classrooms import room_data

router = APIRouter(prefix='/api', tags=['Dashboards and deterministic progress'])


def accessible_activities(db, user, ids):
    query = select(Activity).where(Activity.classroom_id.in_(ids))
    if user.role == 'student':
        query = query.where(Activity.status != 'draft', or_(Activity.kind != 'competition', Activity.id.in_(select(Participant.activity_id).where(Participant.user_id == user.id))))
    return list(db.scalars(query))


def accessible_submissions(db, user, ids):
    query = select(Submission).join(ActivityItem).join(Activity).where(Activity.classroom_id.in_(ids))
    if user.role == 'student':
        query = query.join(SubmissionMember, SubmissionMember.submission_id == Submission.id).where(SubmissionMember.user_id == user.id)
    return list(db.scalars(query.order_by(Submission.created_at)))


@router.get('/dashboard')
def dashboard(db: Db, user: Actor):
    ids = classroom_ids(db, user)
    activities = accessible_activities(db, user, ids)
    submissions = accessible_submissions(db, user, ids)
    visible = [s for s in submissions if grade_visible(user, s, db.get(Activity, db.get(ActivityItem, s.activity_item_id).activity_id))]
    open_activities = [a for a in activities if phase(a) in ('upcoming', 'active')]
    open_activities.sort(key=lambda a: (0 if phase(a) == 'active' else 1, a.ends_at or a.starts_at or 2**62))
    active_competition = next((a for a in open_activities if a.kind == 'competition' and phase(a) == 'active'), None) if user.role == 'student' else None
    return {
        'server_now': now_ms(), 'classrooms': [room_data(db, c) for c in db.scalars(select(Classroom).where(Classroom.id.in_(ids)))],
        'upcoming': [activity_data(db, a) for a in open_activities[:8]],
        'recent_activities': [activity_data(db, a) for a in sorted(activities, key=lambda a: a.created_at, reverse=True)[:6]],
        'feedback': [submission_data(db, user, s) for s in sorted(visible, key=lambda s: s.graded_at or 0, reverse=True)[:5] if s.status != 'submitted'],
        'pending_reviews': sum(1 for s in submissions if s.status == 'submitted') if staff(user) else None,
        'attempts': len(submissions), 'reviewed': sum(1 for s in visible if s.status != 'submitted'),
        'notifications_unread': db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user.id, Notification.read.is_(False))),
        'active_competition': activity_data(db, active_competition) if active_competition else None,
    }


@router.get('/progress')
def progress(db: Db, user: Actor, classroom_id: str | None = None):
    ids = classroom_ids(db, user)
    if classroom_id:
        classroom_access(db, user, classroom_id)
        ids = [classroom_id]
    submissions = accessible_submissions(db, user, ids)
    activities = accessible_activities(db, user, ids)
    activity_map = {a.id: a for a in activities}
    item_map = {i.id: i for i in db.scalars(select(ActivityItem).where(ActivityItem.activity_id.in_(activity_map.keys())))}
    # Latest attempt per participant/task: resubmissions never inflate completion.
    latest: dict[tuple[str, str], Submission] = {}
    for submission in submissions:
        members = list(db.scalars(select(SubmissionMember.user_id).where(SubmissionMember.submission_id == submission.id)))
        for member in members:
            if user.role != 'student' or member == user.id:
                latest[(member, submission.activity_item_id)] = submission
    topics: dict[str, dict] = {}
    people: dict[str, dict] = {}
    if staff(user):
        student_ids = list(db.scalars(select(Membership.user_id).where(Membership.classroom_id.in_(ids)).distinct()))
    else:
        student_ids = [user.id]
    for student_id in student_ids:
        student = db.get(User, student_id)
        assigned = 0
        student_rooms = set(db.scalars(select(Membership.classroom_id).where(Membership.user_id == student_id)))
        for item in item_map.values():
            activity = activity_map[item.activity_id]
            if activity.classroom_id not in student_rooms or not item_is_visible(activity, item):
                continue
            if activity.kind == 'competition' and not db.get(Participant, (activity.id, student_id)):
                continue
            assigned += 1
        people[student_id] = {'id': student_id, 'name': student.display_name, 'assigned': assigned, 'attempted': 0, 'reviewed': 0, 'completed': 0, 'score': 0.0, 'possible': 0.0}
    timeline: dict[str, dict] = {}
    difficulty: dict[str, dict] = {}
    completed = reviewed = 0
    score_total = possible = 0.0
    for (student_id, item_id), submission in latest.items():
        if item_id not in item_map:
            continue
        item = item_map[item_id]
        activity = activity_map[item.activity_id]
        topic_id = item.snapshot.get('topic_id') or 'unassigned'
        if topic_id not in topics:
            topic = db.get(Topic, topic_id) if topic_id != 'unassigned' else None
            room = db.get(Classroom, activity.classroom_id)
            topics[topic_id] = {'id': topic_id, 'name': topic.name if topic else {}, 'subject_id': room.subject_id, 'attempted': 0, 'reviewed': 0, 'score': 0.0, 'possible': 0.0}
        topics[topic_id]['attempted'] += 1
        if student_id in people:
            people[student_id]['attempted'] += 1
        day = datetime.fromtimestamp(submission.created_at / 1000, timezone.utc).date().isoformat()
        timeline.setdefault(day, {'date': day, 'attempted': 0, 'reviewed': 0})['attempted'] += 1
        if not grade_visible(user, submission, activity) or submission.status == 'submitted':
            continue
        reviewed += 1
        completed += int(submission.status == 'reviewed')
        points = submission.score or 0
        score_total += points
        possible += item.points
        topics[topic_id]['reviewed'] += 1
        topics[topic_id]['score'] += points
        topics[topic_id]['possible'] += item.points
        timeline[day]['reviewed'] += 1
        if student_id in people:
            people[student_id]['reviewed'] += 1
            people[student_id]['completed'] += int(submission.status == 'reviewed')
            people[student_id]['score'] += points
            people[student_id]['possible'] += item.points
        difficulty.setdefault(item.id, {'id': item.id, 'title': item.snapshot['title'], 'activity_id': activity.id, 'reviewed': 0, 'score': 0.0, 'possible': 0.0})
        difficulty[item.id]['reviewed'] += 1
        difficulty[item.id]['score'] += points
        difficulty[item.id]['possible'] += item.points
    history = []
    for activity in activities:
        if activity.kind == 'competition' and phase(activity) == 'ended':
            history.append(activity_data(db, activity))
    return {'attempts': len(submissions), 'attempted': len(latest), 'completed': completed, 'reviewed': reviewed, 'score': score_total, 'possible': possible,
        'topics': list(topics.values()), 'students': list(people.values()) if staff(user) else [], 'timeline': sorted(timeline.values(), key=lambda r: r['date'])[-30:],
        'difficulty': sorted(difficulty.values(), key=lambda r: r['score'] / r['possible'])[:8] if staff(user) else [],
        'competition_history': history, 'feedback': [submission_data(db, user, s) for s in reversed(submissions) if grade_visible(user, s, activity_map[item_map[s.activity_item_id].activity_id]) and s.status != 'submitted'][:30]}


@router.get('/notifications')
def notifications(db: Db, user: Actor):
    return [columns(n, 'id', 'kind', 'title', 'link', 'read', 'created_at') for n in db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(100))]


@router.post('/notifications/read')
def mark_notifications_read(db: Db, user: Actor):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read.is_(False)).values(read=True))
    return {'ok': True}


@router.get('/admin/audit')
def audit_log(db: Db, user: Actor):
    require(user.role == 'admin')
    from ..models import AuditLog
    return [dict(columns(a, 'id', 'action', 'entity_id', 'created_at'), actor_name=db.get(User, a.actor_id).display_name if a.actor_id else '') for a in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200))]
