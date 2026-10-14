"""V2 post-M1 teaching and private invitation regression checks."""
from __future__ import annotations
from urllib.parse import urlsplit
from sqlalchemy import select
from server.models import Activity, ActivityItem, EnrollmentInvitation, Membership


def test_existing_student_invite_requires_owner_consent(env):
    teacher, student, wrong = env.client('teacher'), env.client('other'), env.client('teammate')
    before = student.get('/api/classrooms').json()
    assert env.rooms['math'] not in [r['id'] for r in before]
    created = teacher.post('/api/invitations', json={'email': 'other@demo.school.test', 'role': 'student', 'classroom_id': env.rooms['math']})
    assert created.status_code == 201, created.text
    info = created.json()
    assert info['kind'] == 'existing_account' and '/#/enroll/' in info['link']
    assert env.rooms['math'] not in [r['id'] for r in student.get('/api/classrooms').json()]
    token = info['link'].split('/#/enroll/', 1)[1]
    payload = {'token': token}
    assert wrong.post('/api/auth/enrollment-preview', json=payload).status_code == 404
    assert wrong.post('/api/auth/enroll', json=payload).status_code == 404
    assert env.client('admin').post('/api/auth/enroll', json=payload).status_code == 404
    assert student.post('/api/auth/enrollment-preview', json=payload).status_code == 200
    joined = student.post('/api/auth/enroll', json=payload)
    assert joined.status_code == 200, joined.text
    assert joined.json()['classroom_id'] == env.rooms['math']
    assert student.post('/api/auth/enroll', json=payload).status_code == 409
    assert env.rooms['math'] in [r['id'] for r in student.get('/api/classrooms').json()]
    with env.app.state.sessions() as db:
        invite = db.scalar(select(EnrollmentInvitation))
        assert invite.accepted_at is not None
        assert db.get(Membership, (env.rooms['math'], env.users['other']))


def test_invite_revoke_and_cross_classroom_teacher_denial(env):
    physics, teacher, student = env.client('physics'), env.client('teacher'), env.client('other')
    body = {'email': 'other@demo.school.test', 'role': 'student', 'classroom_id': env.rooms['math']}
    assert physics.post('/api/invitations', json=body).status_code == 404
    created = teacher.post('/api/invitations', json=body).json()
    token = created['link'].split('/#/enroll/')[1]
    assert student.post('/api/auth/enroll', json={'token': token+'bad'}).status_code == 404
    assert physics.delete('/api/enrollment-invitations/'+created['id']).status_code == 403
    assert teacher.delete('/api/enrollment-invitations/'+created['id']).status_code == 200
    assert student.post('/api/auth/enroll', json={'token': token}).status_code in (404, 409)
    assert env.rooms['math'] not in [r['id'] for r in student.get('/api/classrooms').json()]


def test_clone_and_edit_are_teacher_only_and_do_not_copy_work(env):
    teacher, student, physics = env.client('teacher'), env.client('student'), env.client('physics')
    original = env.assignment
    assert student.post('/api/activities/'+original+'/clone').status_code == 404
    assert physics.post('/api/activities/'+original+'/clone').status_code == 404
    clone = teacher.post('/api/activities/'+original+'/clone')
    assert clone.status_code == 201, clone.text
    copy = clone.json(); aid = copy['id']
    assert copy['status'] == 'draft' and copy['starts_at'] is None
    assert copy['edit_version'] == 1
    assert student.get('/api/activities/'+aid).status_code == 404
    with env.app.state.sessions() as db:
        source_items = list(db.scalars(select(ActivityItem).where(ActivityItem.activity_id==original).order_by(ActivityItem.position)))
        copy_items = list(db.scalars(select(ActivityItem).where(ActivityItem.activity_id==aid).order_by(ActivityItem.position)))
        assert [x.snapshot for x in copy_items] == [x.snapshot for x in source_items]
        assert all(x.id not in [a.id for a in source_items] for x in copy_items)
    body={'edit_version':1,'title':{'en':'Updated, private draft'},'description':{},'starts_at':None,'ends_at':None,'duration_minutes':60}
    assert student.patch('/api/activities/'+aid+'/draft',json=body).status_code == 404
    updated=teacher.patch('/api/activities/'+aid+'/draft',json=body)
    assert updated.status_code == 200, updated.text
    assert updated.json()['edit_version'] == 2
    assert teacher.patch('/api/activities/'+aid+'/draft',json=body).status_code == 409
    assert env.publish(aid)['status'] == 'published'
    body['edit_version'] = 2
    assert teacher.patch('/api/activities/'+aid+'/draft',json=body).status_code == 409
    assert student.get('/api/activities/'+aid).status_code == 200


def test_review_queue_is_bounded_ordered_and_private(env):
    teacher, other_teacher, student = env.client('teacher'), env.client('physics'), env.client()
    one=env.submit().json()['id']
    two=env.submit().json()['id']
    assert student.get('/api/reviews/queue').status_code == 403
    queue=teacher.get('/api/reviews/queue?status=submitted&limit=1')
    assert queue.status_code==200, queue.text
    assert len(queue.json()['items'])==1 and queue.json()['next_cursor']
    cursor=queue.json()['next_cursor']
    later=teacher.get('/api/reviews/queue',params={'status':'submitted','limit':1,'cursor':cursor})
    assert later.status_code==200
    assert queue.json()['items'][0]['id']!=later.json()['items'][0]['id']
    assert {queue.json()['items'][0]['id'],later.json()['items'][0]['id']}=={one,two}
    assert teacher.get('/api/reviews/queue?cursor=invalid').status_code==422
    assert teacher.get('/api/reviews/queue?limit=999').status_code==422
    assert other_teacher.get('/api/reviews/queue?classroom_id='+env.rooms['math']).status_code==404
    assert other_teacher.get('/api/reviews/queue').json()['items']==[]


def test_staff_preflight_and_audited_admin_only_exception(env):
    from server.models import AuditLog, Notification, now_ms
    teacher, student, admin = env.client('teacher'), env.client('student'), env.client('admin')
    aid = env.create_activity('competition', eligible_ids=[env.users['student']])
    env.publish(aid)
    assert student.get(f'/api/activities/{aid}/preflight').status_code in (403, 404)
    ready = teacher.get(f'/api/activities/{aid}/preflight')
    assert ready.status_code == 200, ready.text
    state = ready.json()
    assert state['item_count'] == 1
    assert state['eligible_participant_count'] == 1
    assert state['checks']['has_items'] and state['checks']['future_deadline']
    old = state['ends_at']
    extension = {'expected_ends_at': old, 'new_ends_at': old+15*60*1000,
        'reason': 'A documented network interruption approved by the school operator.'}
    assert teacher.post(f'/api/activities/{aid}/interruption-extension', json=extension).status_code == 403
    too_long = dict(extension, new_ends_at=old+2*60*60*1000+1)
    assert admin.post(f'/api/activities/{aid}/interruption-extension', json=too_long).status_code == 422
    changed = admin.post(f'/api/activities/{aid}/interruption-extension', json=extension)
    assert changed.status_code == 200, changed.text
    assert changed.json()['ends_at'] == old+15*60*1000
    assert admin.post(f'/api/activities/{aid}/interruption-extension', json=extension).status_code == 409
    with env.app.state.sessions() as db:
        event=db.scalar(select(AuditLog).where(AuditLog.action=='activity.interruption_extension'))
        assert event and event.actor_id == env.users['admin']
        assert event.detail['old_ends_at']==old
        assert 'network interruption' in event.detail['reason']
        assert db.scalar(select(Notification).where(Notification.user_id == env.users['student'],
            Notification.kind=='activity_window_extended'))
        current=db.get(Activity, aid)
        current.ends_at=now_ms()-1000
        db.commit()
    expired = dict(extension, expected_ends_at=old+15*60*1000, new_ends_at=old+16*60*1000)
    assert admin.post(f'/api/activities/{aid}/interruption-extension', json=expired).status_code == 409
    assert student.get('/api/activities/'+aid).status_code == 200


def test_set_copy_is_scoped_to_owner_and_keeps_original_intact(env):
    from server.models import ProblemSet, SetItem
    teacher, student, physics=env.client('teacher'),env.client('student'),env.client('physics')
    created=teacher.post('/api/sets', json={'classroom_id':env.rooms['math'],
        'title':{'en':'Original'},'problem_ids':[env.problems[0]]})
    assert created.status_code==201,created.text
    first=created.json()['id']
    assert student.post('/api/sets/'+first+'/clone').status_code==404
    assert physics.post('/api/sets/'+first+'/clone').status_code==404
    result=teacher.post('/api/sets/'+first+'/clone')
    assert result.status_code==201,result.text
    second=result.json()['id'];assert first!=second
    with env.app.state.sessions() as db:
        a,b=db.get(ProblemSet,first),db.get(ProblemSet,second)
        assert a.classroom_id==b.classroom_id==env.rooms['math']
        assert a.title==b.title
        assert list(db.scalars(select(SetItem.problem_id).where(SetItem.set_id==first)))==list(db.scalars(select(SetItem.problem_id).where(SetItem.set_id==second)))
