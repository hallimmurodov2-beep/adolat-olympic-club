"""Owner-only plans and circle-local capabilities; server time controls all peer content."""
from __future__ import annotations
import hashlib
import json
import re
from urllib.parse import urlsplit
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from ..errors import DomainError, require
from ..models import (User, SubjectMembership, TrainingCircle, CircleMember, TrainingCycle,
                      TrainingPlan, TrainingItem, PracticeEntry, PeerPost, now_ms)
from .access import competing
from .serialize import columns


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def eligible(db: Session, user: User, lock: bool = False) -> None:
    if lock:
        db.execute(update(User).where(User.id == user.id).values(active=User.active).execution_options(synchronize_session=False))
    actor = db.get(User, user.id, populate_existing=True)
    member = db.get(SubjectMembership, ('informatics', user.id), populate_existing=True)
    require(actor is not None and actor.active and actor.role == 'student' and member is not None and member.active, 'subject_required', 403)


def can_train(db: Session, user: User) -> bool:
    m = db.get(SubjectMembership, ('informatics', user.id))
    return user.active and user.role == 'student' and m is not None and m.active


def lock_row(db, cls, row_id):
    # Portable short no-op UPDATE obtains a write lock on SQLite and row lock on PG.
    db.execute(update(cls).where(cls.id == row_id).values(version=cls.version).execution_options(synchronize_session=False))
    return db.get(cls, row_id, populate_existing=True)


def cas(db, cls, record, version, **changes):
    changes['version'] = version + 1
    if hasattr(cls, 'updated_at'):
        changes['updated_at'] = now_ms()
    result = db.execute(update(cls).where(cls.id == record.id, cls.version == version).values(**changes).execution_options(synchronize_session=False))
    require(result.rowcount == 1, 'conflict', 409)
    db.refresh(record)
    return record


def circle_access(db, user, circle_id, manage=False, write=False, allow_locked=False):
    require(not competing(db, user), 'competition_locked', 403)
    if user.role != 'admin':
        eligible(db, user, lock=write)
    circle = lock_row(db, TrainingCircle, circle_id) if write else db.get(TrainingCircle, circle_id)
    require(circle is not None, 'not_found', 404)
    membership = db.get(CircleMember, (circle_id, user.id), populate_existing=True)
    if user.role != 'admin':
        require(membership is not None and membership.status == 'active', 'not_found', 404)
        if manage:
            require(membership.role == 'facilitator', 'forbidden', 403)
    if not allow_locked:
        require(not circle.locked, 'circle_locked', 409)
    if write:
        require(not circle.archived, 'circle_archived', 409)
    return circle, membership


def cycle_access(db, user, cycle_id, write=False, manage=False):
    cycle = db.get(TrainingCycle, cycle_id)
    require(cycle is not None, 'not_found', 404)
    if cycle.owner_id:
        require(cycle.owner_id == user.id, 'not_found', 404)
        if write:
            eligible(db, user, lock=True)
    else:
        circle, member = circle_access(db, user, cycle.circle_id, manage=manage, write=write)
        require(cycle.status != 'draft' or user.role == 'admin' or member.role == 'facilitator', 'not_found', 404)
    if write:
        cycle = lock_row(db, TrainingCycle, cycle.id)
        require(cycle.status != 'cancelled', 'cycle_closed', 409)
    return cycle


def discussion_access(db, user, cycle_id, write=False):
    cycle = cycle_access(db, user, cycle_id, write=write)
    require(cycle.circle_id is not None, 'not_found', 404)
    # Administrators never receive an ordinary live-practice bypass. Reports give
    # staff a separate audited incident-review path, not an early discussion room.
    require(cycle.status == 'published', 'cycle_closed', 409)
    require(cycle.discussion_opens_at is not None and now_ms() >= cycle.discussion_opens_at, 'discussion_locked', 409)
    return cycle


def plan_access(db, user, plan_id, write=False):
    plan = db.get(TrainingPlan, plan_id)
    require(plan is not None and plan.user_id == user.id, 'not_found', 404)
    if write:
        eligible(db, user, lock=True)
        cycle_access(db, user, plan.cycle_id, write=True)
        plan = lock_row(db, TrainingPlan, plan.id)
    return plan


def plan_writable(db, user, plan):
    if not can_train(db, user):
        return False
    cycle = db.get(TrainingCycle, plan.cycle_id)
    if cycle.status == 'cancelled':
        return False
    if not cycle.circle_id:
        return True
    circle = db.get(TrainingCircle, cycle.circle_id)
    member = db.get(CircleMember, (cycle.circle_id, user.id))
    return bool(member and member.status == 'active' and not circle.archived and not circle.locked and not competing(db, user))


def item_access(db, user, item_id, write=False):
    item = db.get(TrainingItem, item_id)
    require(item is not None, 'not_found', 404)
    plan_access(db, user, item.plan_id, write=write)
    return db.get(TrainingItem, item_id, populate_existing=write)


def entry_data(entry):
    return columns(entry, 'id', 'item_id', 'outcome', 'assistance', 'reflection', 'next_step', 'occurred_at', 'created_at', 'version')


def item_data(item):
    return columns(item, 'id', 'plan_id', 'title', 'url', 'provider', 'problem_key', 'status', 'position', 'carried_from_id', 'version', 'created_at', 'updated_at')


def plan_data(db, user, plan, detail=True):
    data = columns(plan, 'id', 'cycle_id', 'goal', 'review', 'next_step', 'context', 'version', 'created_at', 'updated_at')
    data['read_only'] = not plan_writable(db, user, plan)
    if detail:
        items = list(db.scalars(select(TrainingItem).where(TrainingItem.plan_id == plan.id).order_by(TrainingItem.position, TrainingItem.id)))
        data['items'] = [item_data(i) for i in items]
        data['entries'] = [entry_data(e) for e in db.scalars(select(PracticeEntry).where(PracticeEntry.item_id.in_([i.id for i in items])).order_by(PracticeEntry.created_at.desc(), PracticeEntry.id.desc()).limit(200))]
    return data


def cycle_data(db, user, cycle):
    data = columns(cycle, 'id', 'circle_id', 'title', 'guidance', 'links', 'starts_at', 'ends_at', 'practice_starts_at', 'practice_ends_at', 'discussion_opens_at', 'mode', 'status', 'version', 'created_at', 'updated_at')
    member = db.get(CircleMember, (cycle.circle_id, user.id)) if cycle.circle_id else None
    data['can_manage'] = cycle.owner_id == user.id or user.role == 'admin' or bool(member and member.role == 'facilitator' and member.status == 'active')
    data['discussion_open'] = bool(cycle.circle_id and cycle.status == 'published' and cycle.discussion_opens_at <= now_ms() and not competing(db, user))
    data['content_frozen'] = bool(cycle.circle_id and cycle.status == 'published' and now_ms() >= cycle.practice_starts_at)
    plan = db.scalar(select(TrainingPlan).where(TrainingPlan.cycle_id == cycle.id, TrainingPlan.user_id == user.id))
    data['my_plan_id'] = plan.id if plan else None
    data['server_now'] = now_ms()
    return data


def circle_summary(db, user, circle):
    data = columns(circle, 'id', 'name', 'description', 'discoverable', 'archived', 'locked', 'version', 'created_at')
    member = db.get(CircleMember, (circle.id, user.id))
    data['my_role'] = member.role if member and member.status == 'active' else None
    data['my_status'] = member.status if member else None
    data['member_count'] = db.scalar(select(func.count()).select_from(CircleMember).where(CircleMember.circle_id == circle.id, CircleMember.status == 'active'))
    return data


def provider_identity(url):
    p = urlsplit(url)
    if p.hostname == 'codeforces.com':
        match = re.fullmatch(r'/problemset/problem/(\d+)/([A-Za-z0-9]+)', p.path.rstrip('/')) or re.fullmatch(r'/contest/(\d+)/problem/([A-Za-z0-9]+)', p.path.rstrip('/'))
        return 'codeforces', f'{int(match[1])}:{match[2]}' if match else None
    if p.hostname in ('electicode.com', 'www.electicode.com'):
        return 'electicode', None
    return None, None


def ensure_subject_participation(db, subject_id: str, user_id: str):
    """Derive a missing participation row; never undo an explicit deactivation."""
    from .leases import insert_ignore
    insert_ignore(db, SubjectMembership, {'subject_id':subject_id, 'user_id':user_id,
                  'active':True, 'joined_at':now_ms(), 'source':'classroom'}, ['subject_id','user_id'])
