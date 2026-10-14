from __future__ import annotations
import io
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from server.models import Activity, Event, Group, GroupMember, User, now_ms
from server.routes.realtime import event_allowed
from server.services.access import classroom_ids
from tests.conftest import PASSWORD

@pytest.mark.parametrize('path',['/auth/me','/dashboard','/classrooms','/problems','/activities','/groups','/submissions','/progress','/notifications','/admin/users'])
def test_anonymous_rejected(env,path):
    response=TestClient(env.app).get('/api'+path)
    assert response.status_code==401
    assert response.json()['error']['code']=='unauthenticated'

@pytest.mark.parametrize('role',['student','teacher'])
def test_admin_controls_not_authorized(env,role):
    client=env.client(role)
    assert client.get('/api/admin/users').status_code==403
    assert client.get('/api/admin/audit').status_code==403
    assert client.put('/api/settings',json={'name':{'en':'Stolen'},'timezone':'UTC'}).status_code==403
    assert client.patch('/api/admin/users/'+env.users['other'],json={'active':False}).status_code==403

@pytest.mark.parametrize('role',['admin','teacher'])
def test_profile_cannot_promote(env,role):
    response=env.client().patch('/api/profile',json={'role':role})
    assert response.status_code==422
    assert env.client().get('/api/auth/me').json()['user']['role']=='student'

@pytest.mark.parametrize('actor,room',[('teacher','physics'),('physics','math')])
def test_teacher_cross_classroom_denied(env,actor,room):
    client=env.client(actor);cid=env.rooms[room]
    assert client.get('/api/classrooms/'+cid).status_code==404
    assert client.post('/api/classrooms/'+cid+'/announcements',json={'body':{'en':'Intrusion'}}).status_code==404
    assert client.get('/api/progress?classroom_id='+cid).status_code==404
    assert client.get('/api/submissions?classroom_id='+cid).status_code==404

@pytest.mark.parametrize('method,path,body',[('post','/classrooms',{'subject_id':'math','name':{'en':'Fake'}}),('post','/topics',{'subject_id':'math','name':{'en':'Fake'}}),('post','/invitations',{'email':'intruder@example.test','role':'teacher'}),('post','/groups',{'classroom_id':'x','activity_item_id':'x','name':'Fake','user_ids':['x']})])
def test_students_cannot_create_teacher_resources(env,method,path,body):
    response=getattr(env.client(),method)('/api'+path,json=body)
    assert response.status_code in (403,404)

def test_csrf_and_origin(env):
    c=env.client()
    assert c.patch('/api/profile',headers={'X-CSRF-Token':''},json={'locale':'en'}).status_code==403
    assert c.patch('/api/profile',headers={'Origin':'https://evil.example'},json={'locale':'en'}).status_code==403
    assert TestClient(env.app).post('/api/auth/login',headers={'Origin':'https://evil.example'},json={'email':'student@demo.school.test','password':PASSWORD}).status_code==403
    assert c.patch('/api/profile',json={'locale':'ru'}).status_code==200

def test_secure_session_cookie_and_no_cache(env):
    response=TestClient(env.app).post('/api/auth/login',json={'email':'student@demo.school.test','password':PASSWORD})
    cookie=response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert 'no-store' in response.headers['cache-control']
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert 'password' not in response.json()['user']

def test_invitation_single_use_and_role_fixed(env):
    teacher=env.client('teacher');student=env.client()
    assert teacher.post('/api/invitations',json={'email':'t@example.test','role':'teacher'}).status_code==403
    created=teacher.post('/api/invitations',json={'email':'new@example.test','role':'student','classroom_id':env.rooms['math']})
    assert created.status_code==201
    token=created.json()['link'].split('/')[-1]
    anon=TestClient(env.app)
    assert anon.post('/api/auth/invitation',json={'token':token}).json()['role']=='student'
    body={'token':token,'display_name':'Новый ученик','password':PASSWORD}
    assert anon.post('/api/auth/register',json={**body,'role':'admin'}).status_code==422
    result=anon.post('/api/auth/register',json=body)
    assert result.status_code==201 and result.json()['user']['role']=='student' and result.json()['user']['locale']=='ru'
    assert len(anon.get('/api/classrooms').json())==1
    assert TestClient(env.app).post('/api/auth/register',json=body).status_code>=400
    assert anon.post('/api/auth/invitation',json={'token':token}).status_code==404

def test_disabled_and_password_changed_sessions_revoke(env):
    one=env.client();two=TestClient(env.app)
    second=two.post('/api/auth/login',json={'email':'student@demo.school.test','password':PASSWORD}).json()
    changed=one.post('/api/auth/password',json={'current_password':PASSWORD,'new_password':'Another-Strong-Passphrase'})
    assert changed.status_code==200 and 'csrf' in changed.json()
    assert two.get('/api/auth/me').status_code==401
    assert one.get('/api/auth/me').status_code==200
    env.client('admin').patch('/api/admin/users/'+env.users['student'],json={'active':False})
    assert one.get('/api/auth/me').status_code==401

def test_private_submissions_and_grades(env):
    env.client('admin').post('/api/classrooms/'+env.rooms['math']+'/members',json={'user_id':env.users['other']})
    result=env.submit();assert result.status_code==201
    sid=result.json()['id'];other=env.client('other')
    assert other.get('/api/submissions/'+sid).status_code==404
    assert env.client('physics').get('/api/submissions/'+sid).status_code==404
    assert other.put('/api/submissions/'+sid+'/grade',json={'score':7,'version':0}).status_code==404
    reviewed=env.client('teacher').put('/api/submissions/'+sid+'/grade',json={'score':6,'criterion_scores':[2,3,1],'version':0,'feedback':{'en':'Private feedback'},'release':False})
    assert reviewed.status_code==200 and reviewed.json()['released'] is False
    own=env.client().get('/api/submissions/'+sid).json()
    assert own['score'] is None and own['feedback']=={} and own['status']=='submitted'
    assert all(s['id']!=sid for s in other.get('/api/submissions').json())

def test_group_privacy_shared_read_only(env):
    env.client('admin').post('/api/classrooms/'+env.rooms['math']+'/members',json={'user_id':env.users['other']})
    other=env.client('other');teacher=env.client('teacher')
    assert other.get('/api/groups/'+env.group).status_code==404
    teacher.patch('/api/groups/'+env.group,json={'shared':True})
    data=other.get('/api/groups/'+env.group)
    assert data.status_code==200 and data.json()['can_edit'] is False
    assert other.put('/api/groups/'+env.group+'/document',json={'content':'takeover','language':'written','revision':data.json()['document']['revision']}).status_code==404
    assert other.post('/api/groups/'+env.group+'/comments',json={'body':'takeover'}).status_code==404
    assert env.client('physics').get('/api/groups/'+env.group).status_code==404

def test_file_privacy_type_validation_and_normalization(env):
    env.client('admin').post('/api/classrooms/'+env.rooms['math']+'/members',json={'user_id':env.users['other']})
    c=env.client();target='/api/files?target_kind=draft&target_id='+env.item
    assert c.post(target,files={'file':('evil.svg',b'<svg onload="alert(1)"/>','image/svg+xml')}).status_code==422
    assert c.post(target,files={'file':('fake.png',b'not an image','image/png')}).status_code==422
    image=Image.new('RGB',(24,24));buf=io.BytesIO();image.save(buf,format='PNG')
    uploaded=c.post(target,files={'file':('proof.png',buf.getvalue(),'image/png')})
    assert uploaded.status_code==201,uploaded.text
    fid=uploaded.json()['id'];assert c.get('/api/files/'+fid).status_code==200
    assert env.client('other').get('/api/files/'+fid).status_code==404
    assert TestClient(env.app).get('/api/files/'+fid).status_code==401
    assert env.submit(file_ids=[fid]).status_code==201
    assert c.delete('/api/files/'+fid).status_code==409
    assert env.submit(handle='other',file_ids=[fid]).status_code==422
    with env.app.state.sessions() as db:
        assert (env.app.state.settings.data_dir/'uploads'/fid).stat().st_mode & 0o777==0o600

def test_upload_deadline_and_limits(env):
    c=env.client();target='/api/files?target_kind=draft&target_id='+env.item
    assert c.post(target,files={'file':('huge.txt',b'a'*(8*1024*1024+1),'text/plain')}).status_code==413
    env.publish(env.assignment,'end')
    assert c.post(target,files={'file':('proof.txt',b'proof','text/plain')}).status_code==409

def test_event_privacy_filter(env):
    with env.app.state.sessions() as db:
        student=db.get(User,env.users['student']);other=db.get(User,env.users['other']);teacher=db.get(User,env.users['teacher']);rooms=set(classroom_ids(db,student))
        private=Event(classroom_id=env.rooms['math'],user_id=student.id,kind='submission',entity_id='abc')
        assert event_allowed(db,student,private,rooms)
        assert not event_allowed(db,other,private,rooms)
        assert event_allowed(db,teacher,private,set(classroom_ids(db,teacher)))
        team=Event(classroom_id=env.rooms['math'],group_id=env.group,kind='group',entity_id=env.group)
        assert not event_allowed(db,other,team,rooms)
        isolated=Event(classroom_id=env.rooms['physics'],kind='classroom',entity_id='abc')
        assert not event_allowed(db,teacher,isolated,set(classroom_ids(db,teacher)))


def test_assigned_snapshot_files_do_not_require_public_library_problem(env):
    teacher=env.client('teacher');student=env.client();pid=env.problems[0]
    problem=teacher.get('/api/problems/'+pid).json()
    keys=['classroom_id','topic_id','title','statement','subtopic','hints','solution','examples','difficulty','source','year','tags','format','published','version']
    body={key:problem[key] for key in keys};body['published']=False
    created=teacher.post('/api/problems',json=body);assert created.status_code==201
    pid=created.json()['id']
    uploaded=teacher.post('/api/files?target_kind=problem&target_id='+pid,files={'file':('statement.txt',b'Frozen statement supplement','text/plain')})
    assert uploaded.status_code==201
    file_id=uploaded.json()['id']
    assert student.get('/api/files/'+file_id).status_code==404
    aid=env.create_activity(items=[{'problem_id':pid,'points':7}]);env.publish(aid)
    assert student.get('/api/files/'+file_id).status_code==200
    assert env.client('other').get('/api/files/'+file_id).status_code==404
    later=teacher.post('/api/files?target_kind=problem&target_id='+pid,files={'file':('later.txt',b'Not included in the snapshot','text/plain')})
    assert later.status_code==201
    # Later supplements may be accessed through the authorized current library
    # problem, but they must not silently enter the assignment's frozen file list.
    frozen=student.get('/api/activities/'+aid).json()['items'][0]['files']
    assert [file['id'] for file in frozen]==[file_id]
