from uuid import uuid4
from sqlalchemy import delete, select
from server.models import Activity, ActivityItem, Event, GroupComment, GroupMember, Membership, SubmissionMember, User, now_ms
from server.routes.realtime import event_allowed
from server.services.access import classroom_ids
from tests.test_v2_training import ok


def test_known_unreleased_group_attachment_and_event_are_denied_until_release(env):
    teacher=env.client('teacher');student=env.client();item=env.items(env.session)[0]['id']
    group=ok(teacher.post('/api/groups',json={'classroom_id':env.rooms['math'],'activity_item_id':item,'name':'Unreleased','user_ids':[env.users['student']]}),201)
    gid=group['id'];upload=ok(teacher.post(f'/api/files?target_kind=group&target_id={gid}',files={'file':('private.txt',b'Unreleased practice material','text/plain')}),201)
    assert student.get('/api/groups/'+gid).status_code==404
    assert student.get('/api/files/'+upload['id']).status_code==404
    with env.app.state.sessions() as db:
        actor=db.get(User,env.users['student'])
        event=Event(kind='group',entity_id=gid,group_id=gid,classroom_id=env.rooms['math'])
        assert not event_allowed(db,actor,event,set(classroom_ids(db,actor)))
    env.publish(env.session,'start')
    assert student.get('/api/files/'+upload['id']).status_code==404
    ok(teacher.post(f'/api/activities/{env.session}/items/{item}/release',json={'action':'problem'}))
    assert student.get('/api/files/'+upload['id']).status_code==200
    assert env.client('other').get('/api/files/'+upload['id']).status_code==404


def test_offboarding_removes_current_group_but_preserves_historical_authorship(env):
    student=env.client();group=ok(student.get('/api/groups/'+env.group));item=group['activity_item_id']
    doc=ok(student.put('/api/groups/'+env.group+'/document',json={'revision':group['document']['revision'],'content':'A collective proof','language':'written'}))
    before=ok(env.submit(item=item,group_id=env.group,group_revision=doc['revision']),201)
    teacher=env.client('teacher')
    ok(teacher.delete(f'/api/classrooms/{env.rooms["math"]}/members/{env.users["teammate"]}'))
    after=ok(env.submit(item=item,group_id=env.group,group_revision=doc['revision']),201)
    with env.app.state.sessions() as db:
        assert db.get(GroupMember,(env.group,env.users['teammate'])) is None
        assert db.get(SubmissionMember,(before['id'],env.users['teammate'])) is not None
        assert db.get(SubmissionMember,(after['id'],env.users['teammate'])) is None


def test_stale_or_disabled_group_slots_do_not_receive_new_authorship(env):
    student=env.client();g=ok(student.get('/api/groups/'+env.group))
    doc=ok(student.put('/api/groups/'+env.group+'/document',json={'revision':g['document']['revision'],'content':'Proof','language':'written'}))
    with env.app.state.sessions() as db:
        # Characterizes upgraded data with a stale current group row.
        db.execute(delete(Membership).where(Membership.classroom_id==env.rooms['math'],Membership.user_id==env.users['teammate']));db.commit()
    result=ok(env.submit(item=g['activity_item_id'],group_id=env.group,group_revision=doc['revision']),201)
    with env.app.state.sessions() as db:assert db.get(SubmissionMember,(result['id'],env.users['teammate'])) is None


def test_301_comments_include_newest_and_all_older_pages(env):
    ids=[]
    with env.app.state.sessions() as db:
        for n in range(301):
            row=GroupComment(group_id=env.group,author_id=env.users['student'],body=f'Comment {n}',created_at=n)
            db.add(row);db.flush();ids.append(row.id)
        db.commit()
    group=ok(env.client().get('/api/groups/'+env.group))
    assert group['comments'][-1]['body']=='Comment 300'
    seen=[c['id'] for c in group['comments']];cursor=group['comments_next_cursor']
    while cursor:
        page=ok(env.client().get(f'/api/groups/{env.group}/comments',params={'cursor':cursor}))
        seen.extend(c['id'] for c in page['items']);cursor=page['next_cursor']
    assert len(seen)==301 and set(ids)==set(seen)


def test_own_receipt_lookup_after_deadline_removal_no_body_or_grades(env):
    client_id=str(uuid4());submission=ok(env.submit(client_id=client_id),201)
    with env.app.state.sessions() as db:
        db.get(Activity,env.assignment).ends_at=now_ms()-1
        db.execute(delete(Membership).where(Membership.classroom_id==env.rooms['math'],Membership.user_id==env.users['student']));db.commit()
    path='/api/submissions/by-client-id/'+client_id
    receipt=ok(env.client().get(path))
    assert receipt['id']==submission['id'] and receipt['accepted']
    assert 'content' not in receipt and 'score' not in receipt
    for who in ('teammate','teacher','admin'):assert env.client(who).get(path).status_code==404
