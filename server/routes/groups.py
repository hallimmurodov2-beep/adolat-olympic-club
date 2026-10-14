from __future__ import annotations
from fastapi import APIRouter, Query
from sqlalchemy import or_, select, update
from ..errors import DomainError, require
from ..models import Activity, ActivityItem, DocumentRevision, Group, GroupComment, GroupDocument, GroupMember, Membership, StoredFile, User, now_ms
from ..schemas import CommentInput, GroupInput, ShareInput, WorkInput
from ..security import Actor, Db
from ..services.access import classroom_access, classroom_ids, competing, group_access, item_access, item_is_visible, lock_open_activity, staff
from ..services.events import audit, emit, notify
from ..services.serialize import columns, file_data, item_data
from .work import validate_language

router = APIRouter(prefix='/api', tags=['Group collaboration'])


def group_summary(db, group: Group) -> dict:
    result = columns(group, 'id', 'classroom_id', 'activity_item_id', 'name', 'shared', 'created_at')
    result['members'] = [columns(u, 'id', 'display_name') for u in db.scalars(select(User).join(GroupMember, GroupMember.user_id == User.id).where(GroupMember.group_id == group.id))]
    document = db.get(GroupDocument, group.id)
    result['revision'] = document.revision
    result['updated_at'] = document.updated_at
    item = db.get(ActivityItem, group.activity_item_id)
    result['problem_title'] = item.snapshot['title']
    result['activity_id'] = item.activity_id
    return result


@router.get('/groups')
def groups(db: Db, user: Actor, classroom_id: str | None = None):
    require(not competing(db, user), 'competition_locked', 403)
    ids = classroom_ids(db, user)
    if classroom_id:
        classroom_access(db, user, classroom_id)
        ids = [classroom_id]
    query = select(Group).where(Group.classroom_id.in_(ids))
    if user.role == 'student':
        query = query.where(or_(Group.shared.is_(True), Group.id.in_(select(GroupMember.group_id).where(GroupMember.user_id == user.id))))
    visible = []
    for group in db.scalars(query.order_by(Group.created_at.desc()).limit(300)):
        item = db.get(ActivityItem, group.activity_item_id)
        activity = db.get(Activity, item.activity_id)
        if staff(user) or item_is_visible(activity, item):
            visible.append(group_summary(db, group))
    return visible


@router.post('/groups', status_code=201)
def create_group(body: GroupInput, db: Db, user: Actor):
    classroom_access(db, user, body.classroom_id, write=True)
    item = db.get(ActivityItem, body.activity_item_id)
    require(item is not None, 'not_found', 404)
    activity = db.get(Activity, item.activity_id)
    require(activity.classroom_id == body.classroom_id, 'invalid_group', 422)
    require(activity.kind != 'competition', 'competition_locked', 403)
    db.execute(update(ActivityItem).where(ActivityItem.id == item.id).values(position=ActivityItem.position).execution_options(synchronize_session=False))
    require(len(set(body.user_ids)) == len(body.user_ids), 'invalid_student', 422)
    for user_id in body.user_ids:
        student = db.get(User, user_id)
        require(student is not None and student.active and student.role == 'student' and db.get(Membership, (body.classroom_id, user_id)) is not None, 'invalid_student', 422)
        existing = db.scalar(select(GroupMember.group_id).join(Group).where(Group.activity_item_id == item.id, GroupMember.user_id == user_id).limit(1))
        require(existing is None, 'already_grouped', 409)
    group = Group(classroom_id=body.classroom_id, activity_item_id=item.id, name=body.name.strip(), shared=body.shared)
    require(bool(group.name), 'invalid_input', 422)
    db.add(group)
    db.flush()
    db.add(GroupDocument(group_id=group.id, language='python' if item.snapshot['format'] == 'code' else 'written'))
    for user_id in body.user_ids:
        db.add(GroupMember(group_id=group.id, user_id=user_id))
    notify(db, body.user_ids, 'group_assigned', {'ru': group.name, 'en': group.name}, '/groups/' + group.id)
    emit(db, 'group', group.id, classroom_id=group.classroom_id, group_id=group.id)
    audit(db, user.id, 'group.created', group.id)
    db.flush()
    return group_summary(db, group)


@router.get('/groups/{group_id}')
def group_detail(group_id: str, db: Db, user: Actor):
    group = group_access(db, user, group_id)
    result = group_summary(db, group)
    item, activity = item_access(db, user, group.activity_item_id)
    result['item'] = item_data(db, user, item, activity)
    from ..services.access import phase
    result['phase'] = phase(activity)
    result['document'] = columns(db.get(GroupDocument, group.id), 'content', 'language', 'revision', 'updated_at', 'updated_by')
    result['can_edit'] = staff(user) or any(member['id'] == user.id for member in result['members'])
    page = comments_page(group.id, db, user)
    result['comments'] = page['items']
    result['comments_next_cursor'] = page['next_cursor']
    result['revisions'] = [dict(columns(r, 'revision', 'content', 'language', 'created_at'), author_name=db.get(User, r.author_id).display_name) for r in db.scalars(select(DocumentRevision).where(DocumentRevision.group_id == group_id).order_by(DocumentRevision.revision.desc()).limit(50))]
    result['files'] = [file_data(f) for f in db.scalars(select(StoredFile).where(StoredFile.target_kind == 'group', StoredFile.target_id == group.id))]
    return result


@router.put('/groups/{group_id}/document')
def save_document(group_id: str, body: WorkInput, db: Db, user: Actor):
    group = group_access(db, user, group_id, write=True)
    item = db.get(ActivityItem, group.activity_item_id)
    activity = db.get(Activity, item.activity_id)
    if user.role == 'student':
        lock_open_activity(db, activity)
    validate_language(item, body.language)
    updated_at = now_ms()
    result = db.execute(update(GroupDocument).where(GroupDocument.group_id == group_id, GroupDocument.revision == body.revision).values(
        content=body.content, language=body.language, revision=GroupDocument.revision + 1, updated_at=updated_at, updated_by=user.id))
    if result.rowcount != 1:
        document = db.get(GroupDocument, group_id)
        raise DomainError('conflict', 409, columns(document, 'content', 'language', 'revision', 'updated_at'))
    db.add(DocumentRevision(group_id=group_id, revision=body.revision + 1, content=body.content, language=body.language, author_id=user.id))
    emit(db, 'group', group.id, classroom_id=group.classroom_id, group_id=group.id)
    return {'revision': body.revision + 1, 'updated_at': updated_at, 'content': body.content, 'language': body.language}


@router.post('/groups/{group_id}/comments', status_code=201)
def comment(group_id: str, body: CommentInput, db: Db, user: Actor):
    group = group_access(db, user, group_id, write=True)
    require(bool(body.body.strip()), 'invalid_input', 422)
    record = GroupComment(group_id=group_id, author_id=user.id, body=body.body.strip())
    db.add(record)
    db.flush()
    emit(db, 'group', group.id, classroom_id=group.classroom_id, group_id=group.id)
    return columns(record, 'id', 'body', 'created_at')


@router.patch('/groups/{group_id}')
def share(group_id: str, body: ShareInput, db: Db, user: Actor):
    group = group_access(db, user, group_id)
    classroom_access(db, user, group.classroom_id, write=True)
    group.shared = body.shared
    audit(db, user.id, 'group.sharing_changed', group.id)
    emit(db, 'group', group.id, classroom_id=group.classroom_id, group_id=group.id)
    return {'shared': group.shared}


@router.get('/groups/{group_id}/comments')
def comments_page(group_id: str, db: Db, user: Actor, cursor: str | None = None, limit: int = Query(50, ge=1, le=100)):
    from ..services.pagination import apply_before, page_cursor
    group_access(db, user, group_id)
    size = limit if isinstance(limit, int) else 50
    query = select(GroupComment, User).join(User, User.id == GroupComment.author_id).where(GroupComment.group_id == group_id)
    query = apply_before(query, GroupComment, cursor)
    rows = list(db.execute(query.order_by(GroupComment.created_at.desc(), GroupComment.id.desc()).limit(size + 1)))
    more = len(rows) > size
    rows = rows[:size]
    return {'items': [dict(columns(c, 'id', 'body', 'created_at'), author_name=u.display_name, author_role=u.role) for c, u in reversed(rows)],
            'next_cursor': page_cursor(rows[-1][0]) if more else None}
