from __future__ import annotations
from fastapi import APIRouter, Query, Request
from sqlalchemy import delete, func, or_, select, update
from ..errors import DomainError, require
from ..models import (User, Subject, SubjectMembership, TrainingCircle, CircleMember, TrainingCycle, TrainingPlan,
                      TrainingItem, PracticeEntry, PeerPost, ModerationReport, now_ms)
from ..schemas_training import (CycleInput, CycleEdit, PlanInput, ItemInput, ItemEdit, EntryInput, CircleInput,
                               CircleEdit, MemberAction, PostInput, ReportInput, ReportResolve, ReasonInput, CircleLock, SubjectInput)
from ..security import Actor, Db, throttle
from ..services import training as service
from ..services.access import competing
from ..services.events import audit, emit, notify
from ..services.serialize import columns
from ..services.pagination import apply_before, page_cursor

router = APIRouter(prefix='/api', tags=['Independent Informatics'])


@router.get('/subjects/mine')
def my_subjects(db: Db, user: Actor):
    return {'items': [dict(subject_id=s.id, name=s.name, active=m.active) for s, m in db.execute(select(Subject, SubjectMembership).join(SubjectMembership, SubjectMembership.subject_id == Subject.id).where(SubjectMembership.user_id == user.id))], 'can_train': service.can_train(db, user), 'server_now': now_ms()}


@router.put('/admin/subjects/{subject_id}/members/{user_id}')
def subject_member(subject_id: str, user_id: str, body: SubjectInput, db: Db, user: Actor):
    require(user.role == 'admin')
    require(db.get(Subject, subject_id) is not None, 'not_found', 404)
    db.execute(update(User).where(User.id == user_id).values(active=User.active))
    target = db.get(User, user_id, populate_existing=True)
    require(target is not None and target.role == 'student', 'invalid_student', 422)
    member = db.get(SubjectMembership, (subject_id, user_id))
    if member:
        member.active = body.active
    else:
        db.add(SubjectMembership(subject_id=subject_id, user_id=user_id, active=body.active, source='admin'))
    audit(db, user.id, 'subject.enrolled' if body.active else 'subject.deactivated', user_id)
    emit(db, 'profile', user_id, user_id=user_id)
    return {'ok': True}


@router.get('/training/plans')
def plans(db: Db, user: Actor, cursor: str | None = None, limit: int = Query(30, ge=1, le=50)):
    query = apply_before(select(TrainingPlan).where(TrainingPlan.user_id == user.id), TrainingPlan, cursor)
    rows = list(db.scalars(query.order_by(TrainingPlan.created_at.desc(), TrainingPlan.id.desc()).limit(limit + 1)))
    return {'items': [service.plan_data(db, user, p, detail=False) for p in rows[:limit]], 'next_cursor': page_cursor(rows[limit - 1]) if len(rows) > limit else None}


@router.get('/training/cycles')
def cycles(db: Db, user: Actor, circle_id: str | None = None, cursor: str | None = None, limit: int = Query(30, ge=1, le=50)):
    if circle_id:
        _, member = service.circle_access(db, user, circle_id)
        query = select(TrainingCycle).where(TrainingCycle.circle_id == circle_id)
        if user.role != 'admin' and member.role != 'facilitator':
            query = query.where(TrainingCycle.status != 'draft')
    else:
        query = select(TrainingCycle).where(TrainingCycle.owner_id == user.id)
    rows = list(db.scalars(service_query := apply_before(query, TrainingCycle, cursor).order_by(TrainingCycle.created_at.desc(), TrainingCycle.id.desc()).limit(limit + 1)))
    return {'items': [service.cycle_data(db, user, c) for c in rows[:limit]], 'next_cursor': page_cursor(rows[limit - 1]) if len(rows) > limit else None}


@router.post('/training/cycles', status_code=201)
def create_cycle(body: CycleInput, db: Db, user: Actor):
    service.eligible(db, user, lock=True)
    if body.circle_id:
        service.circle_access(db, user, body.circle_id, manage=True, write=True)
    existing = db.get(TrainingCycle, str(body.client_id))
    if existing:
        require(existing.owner_id == user.id or (existing.circle_id == body.circle_id and body.circle_id is not None), 'conflict', 409)
        return service.cycle_data(db, user, existing)
    count = db.scalar(select(func.count()).select_from(TrainingCycle).where(TrainingCycle.owner_id == user.id, TrainingCycle.ends_at > now_ms()))
    require(count < 20, 'training_limit', 409)
    values = body.model_dump(mode='json', exclude={'client_id'})
    cycle = TrainingCycle(id=str(body.client_id), owner_id=None if body.circle_id else user.id, **values)
    db.add(cycle)
    db.flush()
    if body.circle_id and body.status == 'published':
        notify_cycle(db, cycle, 'training_cycle')
    audit(db, user.id, 'training.cycle_created', cycle.id)
    return service.cycle_data(db, user, cycle)


def notify_cycle(db, cycle, kind):
    # Generic, body-free notifications; no gated content or private goals are copied.
    members = list(db.scalars(select(CircleMember.user_id).where(CircleMember.circle_id == cycle.circle_id, CircleMember.status == 'active')))
    notify(db, members, kind, {}, '/training/cycles/' + cycle.id)


@router.get('/training/cycles/{cycle_id}')
def get_cycle(cycle_id: str, db: Db, user: Actor):
    return service.cycle_data(db, user, service.cycle_access(db, user, cycle_id))


@router.patch('/training/cycles/{cycle_id}')
def edit_cycle(cycle_id: str, body: CycleEdit, db: Db, user: Actor):
    cycle = service.cycle_access(db, user, cycle_id, write=True, manage=True)
    require(body.circle_id == cycle.circle_id and str(body.client_id) == cycle.id, 'invalid_input', 422)
    if cycle.circle_id and cycle.status == 'published':
        require(body.status in ('published', 'cancelled'), 'cycle_frozen', 409)
        if now_ms() >= cycle.practice_starts_at:
            frozen = ['title', 'guidance', 'links', 'mode', 'starts_at', 'practice_starts_at']
            values = body.model_dump(mode='json')
            require(all(values[k] == getattr(cycle, k) for k in frozen), 'cycle_frozen', 409)
            require(body.discussion_opens_at >= cycle.discussion_opens_at and body.practice_ends_at >= cycle.practice_ends_at, 'discussion_locked', 409)
    values = body.model_dump(mode='json', exclude={'client_id', 'circle_id', 'version'})
    service.cas(db, TrainingCycle, cycle, body.version, **values)
    if cycle.circle_id:
        notify_cycle(db, cycle, 'training_updated')
    audit(db, user.id, 'training.cycle_updated', cycle.id)
    return service.cycle_data(db, user, cycle)


@router.get('/training/cycles/{cycle_id}/my-plan')
def my_plan(cycle_id: str, db: Db, user: Actor):
    service.cycle_access(db, user, cycle_id)
    plan = db.scalar(select(TrainingPlan).where(TrainingPlan.cycle_id == cycle_id, TrainingPlan.user_id == user.id))
    return service.plan_data(db, user, plan) if plan else None


@router.put('/training/cycles/{cycle_id}/my-plan')
def save_plan(cycle_id: str, body: PlanInput, db: Db, user: Actor):
    service.eligible(db, user, lock=True)
    cycle = service.cycle_access(db, user, cycle_id, write=True)
    plan = db.scalar(select(TrainingPlan).where(TrainingPlan.cycle_id == cycle_id, TrainingPlan.user_id == user.id))
    values = body.model_dump(exclude={'version'})
    if plan:
        service.cas(db, TrainingPlan, plan, body.version, **values)
    else:
        require(body.version == 0, 'conflict', 409)
        plan = TrainingPlan(cycle_id=cycle.id, user_id=user.id, context={'title': cycle.title, 'starts_at': cycle.starts_at, 'ends_at': cycle.ends_at, 'circle_id': cycle.circle_id}, **values)
        db.add(plan)
        db.flush()
    return service.plan_data(db, user, plan)


@router.get('/training/plans/{plan_id}')
def get_plan(plan_id: str, db: Db, user: Actor):
    # Retained own context stays readable after leaving a circle. No current roster/post data.
    return service.plan_data(db, user, service.plan_access(db, user, plan_id))


@router.delete('/training/plans/{plan_id}')
def delete_plan(plan_id: str, db: Db, user: Actor):
    plan = service.plan_access(db, user, plan_id)
    db.delete(plan)
    audit(db, user.id, 'training.plan_deleted', plan.id)
    return {'ok': True}


@router.post('/training/plans/{plan_id}/items', status_code=201)
def create_item(plan_id: str, body: ItemInput, db: Db, user: Actor):
    plan = service.plan_access(db, user, plan_id, write=True)
    existing = db.scalar(select(TrainingItem).where(TrainingItem.plan_id == plan.id, TrainingItem.client_id == str(body.client_id)))
    if existing:
        require(existing.title == body.title and existing.url == body.url, 'idempotency_mismatch', 409)
        return service.item_data(existing)
    if body.carried_from_id:
        service.item_access(db, user, body.carried_from_id)
    count = db.scalar(select(func.count()).select_from(TrainingItem).where(TrainingItem.plan_id == plan.id))
    require(count < 20, 'training_limit', 409)
    provider, problem_key = service.provider_identity(body.url)
    item = TrainingItem(plan_id=plan.id, title=body.title, url=body.url, client_id=str(body.client_id), provider=provider, problem_key=problem_key, position=count, carried_from_id=body.carried_from_id)
    db.add(item)
    db.flush()
    return service.item_data(item)


@router.patch('/training/items/{item_id}')
def edit_item(item_id: str, body: ItemEdit, db: Db, user: Actor):
    item = service.item_access(db, user, item_id, write=True)
    provider, key = service.provider_identity(body.url)
    service.cas(db, TrainingItem, item, body.version, **body.model_dump(exclude={'version'}), provider=provider, problem_key=key)
    return service.item_data(item)


@router.delete('/training/items/{item_id}')
def delete_item(item_id: str, db: Db, user: Actor, version: int = Query(ge=1)):
    item = service.item_access(db, user, item_id, write=True)
    require(item.version == version, 'conflict', 409)
    db.delete(item)
    return {'ok': True}


@router.post('/training/items/{item_id}/entries', status_code=201)
def create_entry(item_id: str, body: EntryInput, db: Db, user: Actor):
    item = service.item_access(db, user, item_id, write=True)
    request_hash = service.fingerprint({'item_id': item_id, **body.model_dump(mode='json')})
    old = db.scalar(select(PracticeEntry).where(PracticeEntry.author_id == user.id, PracticeEntry.client_id == str(body.client_id)))
    if old:
        require(old.request_hash == request_hash, 'idempotency_mismatch', 409)
        return {'entry': service.entry_data(old), 'item': service.item_data(item)}
    service.cas(db, TrainingItem, item, body.item_version, status=body.outcome)
    entry = PracticeEntry(item_id=item.id, author_id=user.id, request_hash=request_hash, **body.model_dump(mode='json', exclude={'item_version'}))
    db.add(entry)
    db.flush()
    return {'entry': service.entry_data(entry), 'item': service.item_data(item)}


@router.get('/training/items/{item_id}/entries')
def entries(item_id: str, db: Db, user: Actor, cursor: str | None = None, limit: int = Query(50, ge=1, le=100)):
    service.item_access(db, user, item_id)
    rows = list(db.scalars(apply_before(select(PracticeEntry).where(PracticeEntry.item_id == item_id), PracticeEntry, cursor).order_by(PracticeEntry.created_at.desc(), PracticeEntry.id.desc()).limit(limit + 1)))
    return {'items': [service.entry_data(e) for e in rows[:limit]], 'next_cursor': page_cursor(rows[limit - 1]) if len(rows) > limit else None}


@router.get('/circles')
def circles(db: Db, user: Actor, cursor: str | None = None, limit: int = Query(30, ge=1, le=50)):
    require(not competing(db, user), 'competition_locked', 403)
    if user.role != 'admin':
        service.eligible(db, user)
    query = select(TrainingCircle)
    if user.role != 'admin':
        query = query.where(or_(TrainingCircle.discoverable.is_(True), TrainingCircle.id.in_(select(CircleMember.circle_id).where(CircleMember.user_id == user.id))))
    rows = list(db.scalars(apply_before(query, TrainingCircle, cursor).order_by(TrainingCircle.created_at.desc(), TrainingCircle.id.desc()).limit(limit + 1)))
    return {'items': [service.circle_summary(db, user, c) for c in rows[:limit]], 'next_cursor': page_cursor(rows[limit - 1]) if len(rows) > limit else None}


@router.post('/circles', status_code=201)
def create_circle(body: CircleInput, request: Request, db: Db, user: Actor):
    require(request.app.state.settings.circles_enabled, 'circles_disabled', 409)
    require(not competing(db, user), 'competition_locked', 403)
    service.eligible(db, user, lock=True)
    existing = db.get(TrainingCircle, str(body.client_id))
    if existing:
        require(existing.created_by == user.id, 'conflict', 409)
        return service.circle_summary(db, user, existing)
    count = db.scalar(select(func.count()).select_from(TrainingCircle).join(CircleMember, CircleMember.circle_id == TrainingCircle.id).where(CircleMember.user_id == user.id, CircleMember.role == 'facilitator', CircleMember.status == 'active', TrainingCircle.archived.is_(False)))
    require(count < 2, 'circle_limit', 409)
    circle = TrainingCircle(id=str(body.client_id), created_by=user.id, **body.model_dump(mode='json', exclude={'client_id'}))
    db.add(circle)
    db.flush()
    db.add(CircleMember(circle_id=circle.id, user_id=user.id, role='facilitator', status='active'))
    db.flush()
    audit(db, user.id, 'circle.created', circle.id)
    return service.circle_summary(db, user, circle)


@router.get('/circles/{circle_id}')
def circle_detail(circle_id: str, db: Db, user: Actor):
    circle, member = service.circle_access(db, user, circle_id, allow_locked=True)
    data = service.circle_summary(db, user, circle)
    data['can_manage'] = user.role == 'admin' or member.role == 'facilitator'
    # Locked-circle shell has no freeform content; staff resolves incidents separately.
    data['members'] = [dict(columns(u, 'id', 'display_name'), role=m.role, status=m.status, transfer_consent=m.transfer_consent) for u, m in db.execute(select(User, CircleMember).join(CircleMember, CircleMember.user_id == User.id).where(CircleMember.circle_id == circle.id, CircleMember.status.in_(['active', 'pending'] if data['can_manage'] else ['active'])))]
    return data


@router.patch('/circles/{circle_id}')
def edit_circle(circle_id: str, body: CircleEdit, db: Db, user: Actor):
    circle, _ = service.circle_access(db, user, circle_id, manage=True, write=True)
    # Circle descriptions could otherwise be used as a pre-debrief message channel.
    active_individual = db.scalar(select(TrainingCycle.id).where(TrainingCycle.circle_id == circle.id, TrainingCycle.mode == 'individual', TrainingCycle.status == 'published', TrainingCycle.practice_starts_at <= now_ms(), TrainingCycle.discussion_opens_at > now_ms()).limit(1))
    if active_individual:
        require(body.name == circle.name and body.description == circle.description, 'cycle_frozen', 409)
    service.cas(db, TrainingCircle, circle, body.version, **body.model_dump(exclude={'version'}))
    audit(db, user.id, 'circle.updated', circle.id)
    return service.circle_summary(db, user, circle)


@router.post('/circles/{circle_id}/join')
def join_circle(circle_id: str, db: Db, user: Actor):
    service.eligible(db, user, lock=True)
    require(not competing(db, user), 'competition_locked', 403)
    circle = service.lock_row(db, TrainingCircle, circle_id)
    require(circle is not None and circle.discoverable, 'not_found', 404)
    require(not circle.archived and not circle.locked, 'circle_locked', 409)
    member = db.get(CircleMember, (circle_id, user.id))
    if not member:
        count = db.scalar(select(func.count()).select_from(CircleMember).where(CircleMember.circle_id == circle_id))
        require(count < 36, 'circle_full', 409)
        db.add(CircleMember(circle_id=circle_id, user_id=user.id))
        staff_ids = list(db.scalars(select(CircleMember.user_id).where(CircleMember.circle_id == circle_id, CircleMember.role == 'facilitator', CircleMember.status == 'active')))
        notify(db, staff_ids, 'circle_join_request', {}, '/circles/' + circle_id)
    return {'status': member.status if member else 'pending'}


@router.post('/circles/{circle_id}/members')
def member_action(circle_id: str, body: MemberAction, db: Db, user: Actor):
    own_consent = body.action in ('consent_transfer', 'decline_transfer') and body.user_id == user.id
    own_remove = body.action == 'remove' and body.user_id == user.id
    if own_remove:
        # Withdrawing consent remains possible for pending, deactivated-subject,
        # locked or archived membership. This grants no access to peer content.
        circle = service.lock_row(db, TrainingCircle, circle_id)
        require(circle is not None, 'not_found', 404)
    else:
        circle, _ = service.circle_access(db, user, circle_id, manage=not own_consent, write=True, allow_locked=user.role == 'admin')
    target = db.get(CircleMember, (circle_id, body.user_id), populate_existing=True)
    require(target is not None, 'not_found', 404)
    if body.action == 'approve':
        service.eligible(db, db.get(User, body.user_id))
        count = db.scalar(select(func.count()).select_from(CircleMember).where(CircleMember.circle_id == circle_id, CircleMember.status == 'active'))
        require(target.status == 'active' or count < 12, 'circle_full', 409)
        target.status = 'active'
        notify(db, [body.user_id], 'circle_joined', {}, '/circles/' + circle_id)
    elif body.action == 'remove':
        facilitators = db.scalar(select(func.count()).select_from(CircleMember).where(CircleMember.circle_id == circle_id, CircleMember.role == 'facilitator', CircleMember.status == 'active'))
        require(target.role != 'facilitator' or facilitators > 1 or circle.archived, 'last_facilitator', 409)
        db.delete(target)
    elif own_consent:
        require(target.status == 'active', 'forbidden', 403)
        target.transfer_consent = body.action == 'consent_transfer'
    elif body.action == 'transfer':
        require(target.status == 'active' and target.transfer_consent and target.user_id != user.id, 'transfer_consent', 409)
        service.eligible(db, db.get(User, body.user_id))
        other_count = db.scalar(select(func.count()).select_from(CircleMember).join(TrainingCircle, TrainingCircle.id == CircleMember.circle_id).where(CircleMember.user_id == body.user_id, CircleMember.role == 'facilitator', TrainingCircle.archived.is_(False)))
        require(other_count < 2, 'circle_limit', 409)
        target.role = 'facilitator'
        target.transfer_consent = False
        actor_member = db.get(CircleMember, (circle_id, user.id))
        if actor_member:
            actor_member.role = 'member'
    else:
        raise DomainError('forbidden', 403)
    audit(db, user.id, 'circle.member_' + body.action, circle.id)
    return {'ok': True}


@router.get('/training/cycles/{cycle_id}/posts')
def posts(cycle_id: str, db: Db, user: Actor, cursor: str | None = None, limit: int = Query(30, ge=1, le=100)):
    service.discussion_access(db, user, cycle_id)
    query = apply_before(select(PeerPost, User).join(User, User.id == PeerPost.author_id).where(PeerPost.cycle_id == cycle_id, PeerPost.hidden.is_(False)), PeerPost, cursor)
    rows = list(db.execute(query.order_by(PeerPost.created_at.desc(), PeerPost.id.desc()).limit(limit + 1)))
    return {'items': [dict(columns(p, 'id', 'kind', 'body', 'created_at'), author_name=u.display_name) for p, u in reversed(rows[:limit])], 'next_cursor': page_cursor(rows[limit - 1][0]) if len(rows) > limit else None}


@router.post('/training/cycles/{cycle_id}/posts', status_code=201)
def post(cycle_id: str, body: PostInput, request: Request, db: Db, user: Actor):
    throttle(db, request.app.state.settings, 'peer-post', user.id, 30, 3600)
    cycle = service.discussion_access(db, user, cycle_id, write=True)
    existing = db.scalar(select(PeerPost).where(PeerPost.author_id == user.id, PeerPost.client_id == str(body.client_id)))
    if existing:
        require(existing.cycle_id == cycle_id and existing.body == body.body and existing.kind == body.kind, 'idempotency_mismatch', 409)
        return columns(existing, 'id', 'created_at')
    row = PeerPost(cycle_id=cycle.id, author_id=user.id, **body.model_dump(mode='json'))
    db.add(row)
    db.flush()
    # Notifications intentionally do not copy post text, title, or author details.
    notify_cycle(db, cycle, 'training_debrief')
    return columns(row, 'id', 'created_at')


@router.post('/training/posts/{post_id}/hide')
def hide_post(post_id: str, body: ReasonInput, db: Db, user: Actor):
    row = db.get(PeerPost, post_id)
    require(row is not None, 'not_found', 404)
    cycle = service.discussion_access(db, user, row.cycle_id)
    service.circle_access(db, user, cycle.circle_id, manage=True, write=True)
    row.hidden = True
    report = ModerationReport(reporter_id=user.id, circle_id=cycle.circle_id, post_id=post_id, reason='facilitator', detail=body.reason)
    db.add(report)
    audit(db, user.id, 'circle.post_hidden', post_id)
    return {'ok': True}


@router.post('/reports', status_code=201)
def report(body: ReportInput, request: Request, db: Db, user: Actor):
    throttle(db, request.app.state.settings, 'report', user.id, 10, 3600)
    service.circle_access(db, user, body.circle_id, allow_locked=True)
    if body.post_id:
        row = db.get(PeerPost, body.post_id)
        require(row is not None, 'not_found', 404)
        cycle = service.discussion_access(db, user, row.cycle_id)
        require(cycle.circle_id == body.circle_id, 'not_found', 404)
    row = ModerationReport(reporter_id=user.id, **body.model_dump())
    db.add(row)
    db.flush()
    audit(db, user.id, 'moderation.reported', row.id)
    return {'id': row.id, 'status': row.status}


@router.get('/reports/mine')
def my_reports(db: Db, user: Actor):
    return {'items': [columns(r, 'id', 'status', 'created_at', 'resolved_at') for r in db.scalars(select(ModerationReport).where(ModerationReport.reporter_id == user.id).order_by(ModerationReport.created_at.desc()).limit(100))]}


@router.get('/admin/reports')
def report_queue(db: Db, user: Actor):
    require(user.role == 'admin')
    audit(db, user.id, 'moderation.queue_viewed', 'reports')
    result = []
    for r in db.scalars(select(ModerationReport).where(ModerationReport.status == 'open').order_by(ModerationReport.created_at).limit(100)):
        data = columns(r, 'id', 'circle_id', 'post_id', 'reason', 'detail', 'status', 'created_at')
        post = db.get(PeerPost, r.post_id) if r.post_id else None
        data['reported_post'] = columns(post, 'body', 'kind', 'created_at') if post else None
        # Reporter identity is not part of queue DTO; incident custodians use audited records.
        result.append(data)
    return {'items': result}


@router.post('/admin/reports/{report_id}/resolve')
def resolve(report_id: str, body: ReportResolve, db: Db, user: Actor):
    require(user.role == 'admin')
    report = db.get(ModerationReport, report_id)
    require(report is not None, 'not_found', 404)
    report.status, report.resolution, report.resolved_by, report.resolved_at = 'resolved', body.reason, user.id, now_ms()
    if body.hide_post and report.post_id:
        db.get(PeerPost, report.post_id).hidden = True
    if body.lock_circle:
        service.lock_row(db, TrainingCircle, report.circle_id).locked = True
    audit(db, user.id, 'moderation.resolved', report.id)
    notify(db, [report.reporter_id], 'report_resolved', {}, '/training')
    return {'ok': True}


@router.post('/admin/circles/{circle_id}/lock')
def lock_circle(circle_id: str, body: CircleLock, db: Db, user: Actor):
    require(user.role == 'admin')
    circle = service.lock_row(db, TrainingCircle, circle_id)
    require(circle is not None, 'not_found', 404)
    circle.locked = body.locked
    db.add(ModerationReport(reporter_id=user.id, circle_id=circle_id, reason='other', detail=body.reason, status='resolved', resolution=body.reason, resolved_by=user.id, resolved_at=now_ms()))
    audit(db, user.id, 'circle.locked' if body.locked else 'circle.unlocked', circle_id)
    return {'ok': True}


@router.get('/me/training-export')
def export_training(db: Db, user: Actor, cursor: str | None = None):
    # A bounded page is intentional; next_cursor is required to export larger histories.
    query = apply_before(select(TrainingPlan).where(TrainingPlan.user_id == user.id), TrainingPlan, cursor)
    rows = list(db.scalars(query.order_by(TrainingPlan.created_at.desc(), TrainingPlan.id.desc()).limit(11)))
    data = []
    for plan in rows[:10]:
        record = service.plan_data(db, user, plan)
        ids = [i['id'] for i in record['items']]
        record['entries'] = [service.entry_data(e) for e in db.scalars(select(PracticeEntry).where(PracticeEntry.item_id.in_(ids), PracticeEntry.author_id == user.id).order_by(PracticeEntry.created_at, PracticeEntry.id).limit(1001))]
        require(len(record['entries']) <= 1000, 'export_too_large', 409)
        data.append(record)
    return {'product': 'Adolat Olympic Club', 'format_version': 1, 'generated_at': now_ms(), 'plans': data, 'next_cursor': page_cursor(rows[9]) if len(rows) > 10 else None}
