from __future__ import annotations
from fastapi import APIRouter
from sqlalchemy import delete, func, select, update
from ..errors import require
from ..models import Activity, Announcement, Classroom, ClubSettings, Group, GroupMember, Membership, Problem, Resource, StoredFile, Subject, Topic, User
from ..schemas import AnnouncementInput, ClassroomEdit, ClassroomInput, ClubInput, MemberInput, ResourceInput, TopicInput
from ..security import Actor, Db
from ..services.access import classroom_access, classroom_ids, staff
from ..services.events import audit, class_students, emit, notify
from ..services.serialize import activity_data, columns, file_data

router = APIRouter(prefix='/api', tags=['Classrooms'])


def room_data(db, room: Classroom) -> dict:
    data = columns(room, 'id', 'subject_id', 'teacher_id', 'name', 'description', 'active', 'created_at')
    data['teacher_name'] = db.get(User, room.teacher_id).display_name
    data['member_count'] = db.scalar(select(func.count()).select_from(Membership).where(Membership.classroom_id == room.id))
    return data


def validate_topic(db, topic_id, subject_id):
    if topic_id:
        topic = db.get(Topic, topic_id)
        require(topic is not None and topic.subject_id == subject_id, 'invalid_topic', 422)


@router.get('/settings')
def get_settings(db: Db, user: Actor):
    return columns(db.get(ClubSettings, 1), 'name', 'timezone')


@router.put('/settings')
def save_settings(body: ClubInput, db: Db, user: Actor):
    require(user.role == 'admin')
    setting = db.get(ClubSettings, 1)
    setting.name, setting.timezone = body.name, body.timezone
    audit(db, user.id, 'settings.updated', '1')
    return columns(setting, 'name', 'timezone')


@router.get('/subjects')
def subjects(db: Db, user: Actor):
    return [{'id': s.id, 'name': s.name, 'topics': [columns(t, 'id', 'subject_id', 'name') for t in db.scalars(select(Topic).where(Topic.subject_id == s.id))]} for s in db.scalars(select(Subject))]


@router.post('/topics', status_code=201)
def create_topic(body: TopicInput, db: Db, user: Actor):
    require(staff(user))
    require(db.get(Subject, body.subject_id) is not None, 'not_found', 404)
    if user.role == 'teacher':
        require(db.scalar(select(Classroom.id).where(Classroom.teacher_id == user.id, Classroom.subject_id == body.subject_id).limit(1)) is not None)
    topic = Topic(**body.model_dump(), created_by=user.id)
    db.add(topic)
    db.flush()
    return columns(topic, 'id', 'subject_id', 'name')


@router.put('/topics/{topic_id}')
def edit_topic(topic_id: str, body: TopicInput, db: Db, user: Actor):
    topic = db.get(Topic, topic_id)
    require(topic is not None, 'not_found', 404)
    require(user.role == 'admin' or (user.role == 'teacher' and topic.created_by == user.id))
    require(topic.subject_id == body.subject_id, 'invalid_topic', 422)
    topic.name = body.name
    return columns(topic, 'id', 'subject_id', 'name')


@router.get('/classrooms')
def classrooms(db: Db, user: Actor):
    return [room_data(db, c) for c in db.scalars(select(Classroom).where(Classroom.id.in_(classroom_ids(db, user))).order_by(Classroom.created_at))]


@router.post('/classrooms', status_code=201)
def create_classroom(body: ClassroomInput, db: Db, user: Actor):
    require(staff(user))
    require(db.get(Subject, body.subject_id) is not None, 'not_found', 404)
    teacher_id = body.teacher_id if user.role == 'admin' and body.teacher_id else user.id
    teacher = db.get(User, teacher_id)
    require(teacher is not None and teacher.active and teacher.role in ('teacher', 'admin'), 'invalid_teacher', 422)
    if user.role == 'teacher':
        require(body.teacher_id in (None, user.id))
    room = Classroom(subject_id=body.subject_id, teacher_id=teacher_id, name=body.name, description=body.description)
    db.add(room)
    db.flush()
    audit(db, user.id, 'classroom.created', room.id)
    return room_data(db, room)


@router.get('/classrooms/{classroom_id}')
def classroom_detail(classroom_id: str, db: Db, user: Actor):
    room = classroom_access(db, user, classroom_id)
    data = room_data(db, room)
    # Only members of this class, never the school's global directory.
    data['members'] = [columns(u, 'id', 'display_name', 'active') for u in db.scalars(select(User).join(Membership, Membership.user_id == User.id).where(Membership.classroom_id == classroom_id))]
    data['announcements'] = [dict(columns(a, 'id', 'body', 'created_at'), author_name=db.get(User, a.author_id).display_name) for a in db.scalars(select(Announcement).where(Announcement.classroom_id == classroom_id).order_by(Announcement.created_at.desc()).limit(50))]
    data['resources'] = []
    for resource in db.scalars(select(Resource).where(Resource.classroom_id == classroom_id).order_by(Resource.created_at.desc()).limit(200)):
        result = columns(resource, 'id', 'title', 'body', 'url', 'topic_id', 'created_at')
        result['files'] = [file_data(f) for f in db.scalars(select(StoredFile).where(StoredFile.target_kind == 'resource', StoredFile.target_id == resource.id))]
        data['resources'].append(result)
    activities = select(Activity).where(Activity.classroom_id == classroom_id).order_by(Activity.created_at.desc())
    if user.role == 'student':
        from ..models import Participant
        from sqlalchemy import or_
        activities = activities.where(Activity.status != 'draft', or_(Activity.kind != 'competition', Activity.id.in_(select(Participant.activity_id).where(Participant.user_id == user.id))))
    data['activities'] = [activity_data(db, a) for a in db.scalars(activities.limit(150))]
    return data


@router.patch('/classrooms/{classroom_id}')
def edit_classroom(classroom_id: str, body: ClassroomEdit, db: Db, user: Actor):
    room = classroom_access(db, user, classroom_id, write=True)
    room.name, room.description, room.active = body.name, body.description, body.active
    emit(db, 'classroom', room.id, classroom_id=room.id)
    audit(db, user.id, 'classroom.updated', room.id)
    return room_data(db, room)


@router.post('/classrooms/{classroom_id}/members', status_code=201)
def add_member(classroom_id: str, body: MemberInput, db: Db, user: Actor):
    require(user.role == 'admin')
    classroom_access(db, user, classroom_id, write=True)
    student = db.get(User, body.user_id)
    require(student is not None and student.active and student.role == 'student', 'invalid_student', 422)
    if db.get(Membership, (classroom_id, student.id)) is None:
        db.add(Membership(classroom_id=classroom_id, user_id=student.id))
    from ..services.training import ensure_subject_participation
    ensure_subject_participation(db, db.get(Classroom, classroom_id).subject_id, student.id)
    audit(db, user.id, 'membership.added', student.id)
    emit(db, 'membership', classroom_id, classroom_id=classroom_id)
    return {'ok': True}


@router.delete('/classrooms/{classroom_id}/members/{student_id}')
def remove_member(classroom_id: str, student_id: str, db: Db, user: Actor):
    classroom_access(db, user, classroom_id, write=True)
    # Share the classroom lock with acceptance of new group submissions.
    db.execute(update(Classroom).where(Classroom.id == classroom_id).values(active=Classroom.active))
    db.execute(delete(GroupMember).where(GroupMember.user_id == student_id, GroupMember.group_id.in_(select(Group.id).where(Group.classroom_id == classroom_id))))
    db.execute(delete(Membership).where(Membership.classroom_id == classroom_id, Membership.user_id == student_id))
    audit(db, user.id, 'membership.removed', student_id)
    emit(db, 'membership', classroom_id, classroom_id=classroom_id)
    return {'ok': True}


@router.post('/classrooms/{classroom_id}/announcements', status_code=201)
def announce(classroom_id: str, body: AnnouncementInput, db: Db, user: Actor):
    room = classroom_access(db, user, classroom_id, write=True)
    announcement = Announcement(classroom_id=classroom_id, author_id=user.id, body=body.body)
    db.add(announcement)
    db.flush()
    notify(db, class_students(db, classroom_id), 'announcement', room.name, '/classrooms/' + classroom_id)
    emit(db, 'classroom', classroom_id, classroom_id=classroom_id)
    return columns(announcement, 'id', 'body', 'created_at')


@router.post('/classrooms/{classroom_id}/resources', status_code=201)
def create_resource(classroom_id: str, body: ResourceInput, db: Db, user: Actor):
    room = classroom_access(db, user, classroom_id, write=True)
    validate_topic(db, body.topic_id, room.subject_id)
    resource = Resource(classroom_id=classroom_id, **body.model_dump())
    db.add(resource)
    db.flush()
    emit(db, 'classroom', classroom_id, classroom_id=classroom_id)
    return columns(resource, 'id', 'title', 'body', 'url', 'topic_id', 'created_at')


@router.put('/resources/{resource_id}')
def edit_resource(resource_id: str, body: ResourceInput, db: Db, user: Actor):
    resource = db.get(Resource, resource_id)
    require(resource is not None, 'not_found', 404)
    room = classroom_access(db, user, resource.classroom_id, write=True)
    validate_topic(db, body.topic_id, room.subject_id)
    for key, value in body.model_dump().items():
        setattr(resource, key, value)
    emit(db, 'classroom', room.id, classroom_id=room.id)
    return columns(resource, 'id', 'title', 'body', 'url', 'topic_id', 'created_at')
