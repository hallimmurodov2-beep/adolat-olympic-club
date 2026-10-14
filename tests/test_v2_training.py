"""Synthetic M1 acceptance tests. No live platform or student data is used."""
from __future__ import annotations
from uuid import uuid4
from sqlalchemy import delete, select
import pytest
from server.models import (Membership, GroupMember, SubjectMembership, TrainingCycle,
                           PracticeEntry, TrainingItem, TrainingPlan, PeerPost, Event, now_ms)


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def make_cycle(env, who='student', circle=None, opened=False, mode='individual'):
    t = now_ms()
    data = {'client_id':str(uuid4()), 'title':{'en':'Graph traversal', 'ru':'Обход графов'},
            'starts_at':t-7200000, 'ends_at':t+86400000}
    if circle:
        data.update(circle_id=circle, mode=mode, practice_starts_at=t-3600000,
                    practice_ends_at=t-10000 if opened else t+600000,
                    discussion_opens_at=t-5000 if opened else t+900000,
                    guidance={'en':'Attempt independently first'}, links=[{'title':'External exercise', 'url':'https://codeforces.com/problemset/problem/4/A'}])
    response = env.client(who).post('/api/training/cycles', json=data)
    return ok(response,201), data


def make_plan(env, cycle, who='student'):
    return ok(env.client(who).put(f'/api/training/cycles/{cycle}/my-plan', json={'version':0, 'goal':{'en':'My private goal'}}))


def make_item(env, plan, who='student', **changes):
    data = {'client_id':str(uuid4()), 'title':'An external exercise', 'url':'https://codeforces.com/problemset/problem/4/A', **changes}
    return ok(env.client(who).post(f'/api/training/plans/{plan}/items',json=data),201), data


def make_circle(env, who='student'):
    return ok(env.client(who).post('/api/circles',json={'client_id':str(uuid4()),'name':{'en':'Graph circle'},'description':{'ru':'Подготовка вместе'}}),201)


def join(env, circle, who='teammate', facilitator='student'):
    assert ok(env.client(who).post(f'/api/circles/{circle}/join'))['status']=='pending'
    return ok(env.client(facilitator).post(f'/api/circles/{circle}/members',json={'action':'approve','user_id':env.users[who]}))


def test_independent_student_no_teacher_no_account_full_loop(env):
    # Membership in the subject is sufficient; teaching rooms and groups are removed.
    with env.app.state.sessions() as db:
        db.execute(delete(GroupMember).where(GroupMember.user_id==env.users['student']))
        db.execute(delete(Membership).where(Membership.user_id==env.users['student']))
        db.commit()
    student=env.client()
    assert ok(student.get('/api/subjects/mine'))['can_train']
    assert ok(student.get('/api/informatics/codeforces/me'))['state']=='not_connected'
    cycle, _=make_cycle(env)
    plan=make_plan(env,cycle['id'])
    item, data=make_item(env,plan['id'],url='https://electicode.com/en/courses')
    # A response-loss retry reuses the same item, not a second queue entry.
    assert ok(student.post(f'/api/training/plans/{plan["id"]}/items',json=data),201)['id']==item['id']
    payload={'client_id':str(uuid4()),'item_version':item['version'],'outcome':'revisit','assistance':'editorial','reflection':{'en':'An invariant was missing'},'next_step':{'ru':'Проверить границы'}}
    entry=ok(student.post(f'/api/training/items/{item["id"]}/entries',json=payload),201)
    again=ok(student.post(f'/api/training/items/{item["id"]}/entries',json=payload),201)
    assert again['entry']['id']==entry['entry']['id']
    assert entry['item']['status']=='revisit'
    assert student.post(f'/api/training/items/{item["id"]}/entries',json={**payload,'outcome':'completed'}).status_code==409
    next_cycle,_=make_cycle(env);next_plan=make_plan(env,next_cycle['id'])
    carried,_=make_item(env,next_plan['id'],carried_from_id=item['id'])
    assert carried['carried_from_id']==item['id']
    original=ok(student.get('/api/training/plans/'+plan['id']))
    assert original['items'][0]['status']=='revisit'
    export=ok(student.get('/api/me/training-export'))
    assert len(export['plans'])==2 and 'An invariant was missing' in str(export)
    assert 'author_id' not in str(export) and 'password' not in str(export)
    with env.app.state.sessions() as db:
        assert len(list(db.scalars(select(PracticeEntry))))==1


@pytest.mark.parametrize('who',['teammate','other','teacher','admin'])
def test_private_plan_is_not_staff_or_peer_resource(env,who):
    cycle,_=make_cycle(env); plan=make_plan(env,cycle['id']);item,_=make_item(env,plan['id'])
    actor=env.client(who)
    assert actor.get('/api/training/plans/'+plan['id']).status_code==404
    assert actor.get(f'/api/training/items/{item["id"]}/entries').status_code==404
    assert actor.delete('/api/training/plans/'+plan['id']).status_code==404
    assert plan['id'] not in str(ok(actor.get('/api/me/training-export')))


@pytest.mark.parametrize('url', ['http://example.com/problem','javascript:alert(1)','data:text/html,hi', 'https://a:b@example.com/x','https://localhost/x','https://127.0.0.1/x','https://[::1]/x','https://example.com:8000/x','https://example.com\\@evil.test/x'])
def test_external_links_reject_unsafe_forms_without_fetching(env,url):
    cycle,_=make_cycle(env);plan=make_plan(env,cycle['id'])
    r=env.client().post(f'/api/training/plans/{plan["id"]}/items',json={'client_id':str(uuid4()),'title':'Resource','url':url})
    assert r.status_code==422,r.text


def test_plan_compare_and_swap_and_queue_limit(env):
    cycle,_=make_cycle(env);plan=make_plan(env,cycle['id']);student=env.client()
    path=f'/api/training/cycles/{cycle["id"]}/my-plan'
    body={'version':plan['version'],'goal':{'ru':'Новая цель'}}
    assert ok(student.put(path,json=body))['version']==plan['version']+1
    assert student.put(path,json=body).status_code==409
    for n in range(20):make_item(env,plan['id'],title=f'Exercise {n}')
    assert student.post(f'/api/training/plans/{plan["id"]}/items',json={'client_id':str(uuid4()),'title':'Overflow','url':'https://example.com/a'}).status_code==409


def test_subject_enrollment_does_not_grant_classroom_access(env):
    other=env.client('other')
    assert not ok(other.get('/api/subjects/mine'))['can_train']
    assert other.post('/api/circles',json={'client_id':str(uuid4()),'name':{'en':'No permission'}}).status_code==403
    path=f'/api/admin/subjects/informatics/members/{env.users["other"]}'
    assert env.client('teacher').put(path,json={'active':True}).status_code==403
    ok(env.client('admin').put(path,json={'active':True}))
    assert ok(other.get('/api/subjects/mine'))['can_train']
    assert other.get('/api/classrooms/'+env.rooms['informatics']).status_code==404
    cycle,_=make_cycle(env,'other');plan=make_plan(env,cycle['id'],'other')
    ok(env.client('admin').put(path,json={'active':False}))
    assert ok(other.get('/api/training/plans/'+plan['id']))['read_only']
    assert other.post(f'/api/training/plans/{plan["id"]}/items',json={'client_id':str(uuid4()),'title':'No write','url':'https://example.com/a'}).status_code==403


def test_circle_opt_in_facilitator_no_global_privileges(env):
    circle=make_circle(env);cid=circle['id'];student=env.client();mate=env.client('teammate')
    discovery=ok(mate.get('/api/circles'))
    assert discovery['items'][0]['member_count']==1
    assert 'members' not in discovery['items'][0] and 'email' not in str(discovery)
    assert mate.get('/api/circles/'+cid).status_code==404
    join(env,cid)
    assert len(ok(mate.get('/api/circles/'+cid))['members'])==2
    assert mate.post(f'/api/circles/{cid}/members',json={'action':'approve','user_id':env.users['student']}).status_code==403
    assert student.get('/api/admin/users').status_code==403
    assert student.post('/api/activities',json={'classroom_id':env.rooms['math'],'kind':'assignment','title':{'en':'Escalation'},'starts_at':now_ms(),'ends_at':now_ms()+10000,'items':[{'problem_id':env.problems[0],'points':7}]}).status_code==404


def test_last_facilitator_transfer_requires_consent(env):
    cid=make_circle(env)['id'];join(env,cid)
    path=f'/api/circles/{cid}/members';student=env.client();mate=env.client('teammate')
    assert student.post(path,json={'action':'remove','user_id':env.users['student']}).status_code==409
    assert student.post(path,json={'action':'transfer','user_id':env.users['teammate']}).status_code==409
    ok(mate.post(path,json={'action':'consent_transfer','user_id':env.users['teammate']}))
    ok(student.post(path,json={'action':'transfer','user_id':env.users['teammate']}))
    assert ok(mate.get('/api/circles/'+cid))['my_role']=='facilitator'
    assert ok(student.get('/api/circles/'+cid))['my_role']=='member'
    ok(student.post(path,json={'action':'remove','user_id':env.users['student']}))
    assert student.get('/api/circles/'+cid).status_code==404


def test_two_circle_creation_limit(env):
    make_circle(env);make_circle(env)
    assert env.client().post('/api/circles',json={'client_id':str(uuid4()),'name':{'en':'Third'}}).status_code==409


def test_spoiler_gate_denies_all_freeform_categories_and_freezes_guidance(env):
    cid=make_circle(env)['id'];join(env,cid);cycle,body=make_cycle(env,circle=cid)
    student=env.client();path=f'/api/training/cycles/{cycle["id"]}/posts'
    # Even a pre-existing record is not disclosed before the gate.
    with env.app.state.sessions() as db:
        db.add(PeerPost(cycle_id=cycle['id'],author_id=env.users['teammate'],kind='logistics',body={'en':'SECRET BEFORE GATE'},client_id=str(uuid4())))
        db.commit()
    for who in ('student','teammate','admin'):
        client=env.client(who)
        assert client.get(path).status_code==409
        for kind in ('help','explanation','logistics'):
            assert client.post(path,json={'client_id':str(uuid4()),'kind':kind,'body':{'en':'Answer'}}).status_code==409
    assert 'SECRET BEFORE GATE' not in str(ok(student.get('/api/notifications')))
    edit={**body,'version':cycle['version'],'guidance':{'en':'A forbidden answer'}}
    assert student.patch('/api/training/cycles/'+cycle['id'],json=edit).status_code==409
    early={**body,'version':cycle['version'],'practice_ends_at':now_ms()+1000,'discussion_opens_at':now_ms()+2000}
    assert student.patch('/api/training/cycles/'+cycle['id'],json=early).status_code==409
    circle=ok(student.get('/api/circles/'+cid))
    assert student.patch('/api/circles/'+cid,json={'version':circle['version'],'name':circle['name'],'description':{'en':'A side-channel answer'}}).status_code==409


def test_open_discussion_moderation_and_removed_member_retained_plan(env):
    cid=make_circle(env)['id'];join(env,cid);cycle,_=make_cycle(env,circle=cid,opened=True)
    student=env.client();mate=env.client('teammate');plan=make_plan(env,cycle['id'],'teammate')
    path=f'/api/training/cycles/{cycle["id"]}/posts';data={'client_id':str(uuid4()),'kind':'help','body':{'en':'Why is this invariant valid?'}}
    post=ok(mate.post(path,json=data),201)
    assert ok(mate.post(path,json=data),201)['id']==post['id']
    assert ok(student.get(path))['items'][0]['body']==data['body']
    assert student.get('/api/training/plans/'+plan['id']).status_code==404
    report=ok(student.post('/api/reports',json={'circle_id':cid,'post_id':post['id'],'reason':'other','detail':'Please review this test'}),201)
    assert mate.get('/api/admin/reports').status_code==403
    queue=ok(env.client('admin').get('/api/admin/reports'))
    assert queue['items'][0]['reported_post']['body']==data['body'] and 'reporter_id' not in str(queue)
    ok(env.client('admin').post(f'/api/admin/reports/{report["id"]}/resolve',json={'reason':'Synthetic test moderation','hide_post':True}))
    assert ok(student.get(path))['items']==[]
    ok(student.post(f'/api/circles/{cid}/members',json={'action':'remove','user_id':env.users['teammate']}))
    assert mate.get(path).status_code==404
    retained=ok(mate.get('/api/training/plans/'+plan['id']))
    assert retained['read_only'] and 'members' not in retained
    assert plan['id'] in str(ok(mate.get('/api/me/training-export')))


def test_collaborative_mode_explicit_opening_and_internal_competition_lock(env):
    cid=make_circle(env)['id'];join(env,cid);cycle,body=make_cycle(env,circle=cid,opened=True,mode='collaborative')
    path=f'/api/training/cycles/{cycle["id"]}/posts'
    assert env.client().get(path).status_code==200
    aid=env.create_activity('competition',eligible_ids=[env.users['student']],starts_at=now_ms()-1000)
    env.publish(aid)
    assert env.client().get(path).status_code==403
    assert env.client().get('/api/circles/'+cid).status_code==403


def test_post_pagination_equal_timestamps_has_no_missing_records(env):
    cid=make_circle(env)['id'];cycle,_=make_cycle(env,circle=cid,opened=True)
    ids=set()
    with env.app.state.sessions() as db:
        for n in range(71):
            p=PeerPost(cycle_id=cycle['id'],author_id=env.users['student'],kind='explanation',body={'en':str(n)},client_id=str(uuid4()),created_at=100)
            db.add(p);db.flush();ids.add(p.id)
        db.commit()
    seen=[];cursor=None
    while True:
        page=ok(env.client().get(f'/api/training/cycles/{cycle["id"]}/posts',params={'limit':20,**({'cursor':cursor} if cursor else {})}))
        seen += [p['id'] for p in page['items']]
        cursor=page['next_cursor']
        if not cursor:break
    assert len(seen)==71 and set(seen)==ids
