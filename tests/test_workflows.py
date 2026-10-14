from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from server.models import Activity, ActivityItem, Draft, GroupDocument, Submission, now_ms
from tests.conftest import PASSWORD

def test_drafts_persist_and_stale_save_is_rejected(env):
    student=env.client();path='/api/drafts/'+env.item
    start=student.get(path).json();body={'content':'Доказательство $n^2$','language':'written','revision':start['revision']}
    save=student.put(path,json=body);assert save.status_code==200
    assert student.get(path).json()['content']==body['content']
    conflict=student.put(path,json={**body,'content':'stale'})
    assert conflict.status_code==409 and conflict.json()['error']['data']['content']==body['content']
    second=TestClient(env.app);second.post('/api/auth/login',json={'email':'student@demo.school.test','password':PASSWORD})
    assert second.get(path).json()['content']==body['content']

def test_immutable_history_and_idempotency(env):
    token=str(uuid.uuid4());one=env.submit(client_id=token,content='Attempt one');assert one.status_code==201
    repeat=env.submit(client_id=token,content='Attempt one');assert repeat.json()['id']==one.json()['id']
    assert env.submit(client_id=token,content='Mutated').status_code==409
    two=env.submit(content='Attempt two');assert two.json()['attempt']==one.json()['attempt']+1
    assert env.client().get('/api/submissions/'+one.json()['id']).json()['content']=='Attempt one'

def test_review_release_history_and_metrics(env):
    before=env.client().get('/api/progress').json();s=env.submit().json();sid=s['id'];teacher=env.client('teacher')
    grade={'score':5,'criterion_scores':[2,2,1],'feedback':{'ru':'Обоснуйте последний переход.','en':'Justify the last step.'},'version':0,'release':False,'status':'revision_requested'}
    assert teacher.put('/api/submissions/'+sid+'/grade',json=grade).status_code==200
    assert env.client().get('/api/submissions/'+sid).json()['feedback']=={}
    assert teacher.put('/api/submissions/'+sid+'/grade',json=grade).status_code==409
    grade.update(version=1,score=7,criterion_scores=[2,4,1],status='reviewed',release=True)
    assert teacher.put('/api/submissions/'+sid+'/grade',json=grade).status_code==200
    student=env.client().get('/api/submissions/'+sid).json();assert student['score']==7 and student['released']
    assert len(teacher.get('/api/submissions/'+sid).json()['grade_history'])==2
    progress=env.client().get('/api/progress').json();assert progress['attempts']==before['attempts']+1
    assert progress['completed']>=1 and progress['score']>=7
    assert any(n['kind']=='grade_released' for n in env.client().get('/api/notifications').json())

@pytest.mark.parametrize('grade',[{'score':8,'version':0},{'score':-1,'version':0},{'score':3,'version':0,'criterion_scores':[3]},{'score':3,'version':0,'graded_by':'teacher'}])
def test_invalid_grade_rejected(env,grade):
    sid=env.submit().json()['id'];response=env.client('teacher').put('/api/submissions/'+sid+'/grade',json=grade)
    assert response.status_code==422

def test_rubric_constraints(env):
    rubric=[{'name':{'ru':'Идея','en':'Idea'},'max':3},{'name':{'ru':'Доказательство','en':'Proof'},'max':4}]
    aid=env.create_activity(items=[{'problem_id':env.problems[0],'points':7,'rubric':rubric}]);env.publish(aid);item=env.items(aid)[0]['id'];sid=env.submit(item=item).json()['id']
    path='/api/submissions/'+sid+'/grade';teacher=env.client('teacher')
    assert teacher.put(path,json={'score':7,'criterion_scores':[4,3],'version':0}).status_code==422
    assert teacher.put(path,json={'score':7,'criterion_scores':[3,3],'version':0}).status_code==422
    good=teacher.put(path,json={'criterion_scores':[3,4],'version':0,'release':True});assert good.status_code==200 and good.json()['score']==7

def test_live_release_help_and_end(env):
    teacher=env.client('teacher');student=env.client();sid=env.session;items=env.items(sid)
    assert student.get('/api/activities/'+sid).status_code==404
    env.publish(sid,'start');assert student.get('/api/activities/'+sid).json()['items']==[]
    assert student.get('/api/drafts/'+items[0]['id']).status_code==404
    released=teacher.post(f'/api/activities/{sid}/items/{items[0]["id"]}/release',json={'action':'problem'});assert released.status_code==200
    visible=student.get('/api/activities/'+sid).json();assert len(visible['items'])==1
    help=student.post('/api/activities/'+sid+'/help',json={'body':'Нужна помощь с идеей.'});assert help.status_code==201
    assert teacher.get('/api/activities/'+sid).json()['help_requests'][0]['body']=='Нужна помощь с идеей.'
    teacher.post('/api/help/'+help.json()['id']+'/resolve');assert student.get('/api/activities/'+sid).json()['help_requests'][0]['resolved']
    assert env.submit(item=items[0]['id']).status_code==201
    env.publish(sid,'end');assert env.submit(item=items[0]['id']).status_code==409

def test_group_saved_revisions_conflict_and_final_snapshot(env):
    student=env.client();teammate=env.client('teammate');path='/api/groups/'+env.group;data=student.get(path).json();rev=data['document']['revision'];item=data['activity_item_id']
    body={'content':'Our collective proof.','language':'written','revision':rev}
    assert student.put(path+'/document',json=body).status_code==200
    stale=teammate.put(path+'/document',json={**body,'content':'stale'})
    assert stale.status_code==409 and stale.json()['error']['data']['revision']==rev+1
    submitted=env.submit(item=item,group_id=env.group,group_revision=rev+1,content='Client forged replacement')
    assert submitted.status_code==201 and submitted.json()['content']=='Our collective proof.'
    assert teammate.get('/api/submissions/'+submitted.json()['id']).status_code==200
    assert env.client('other').get('/api/submissions/'+submitted.json()['id']).status_code==404
    updated=student.get(path).json();assert updated['revisions'][0]['content']==body['content']
    assert env.submit(item=item,group_id=env.group,group_revision=rev).status_code==409

def test_group_assignment_duplicate_and_unreleased_privacy(env):
    teacher=env.client('teacher');item=env.items(env.session)[0]['id']
    body={'classroom_id':env.rooms['math'],'activity_item_id':item,'name':'Secret Team','user_ids':[env.users['student']]}
    created=teacher.post('/api/groups',json=body);assert created.status_code==201
    gid=created.json()['id'];assert all(g['id']!=gid for g in env.client().get('/api/groups').json())
    assert teacher.post('/api/groups',json=body).status_code==409

def test_deadlines_use_server_time(env):
    aid=env.create_activity();env.publish(aid);item=env.items(aid)[0]['id'];student=env.client()
    assert env.submit(item=item).status_code==201
    with env.app.state.sessions() as db:
        a=db.get(Activity,aid);a.ends_at=now_ms()-1;db.commit()
    assert student.put('/api/drafts/'+item,json={'content':'late','language':'written','revision':0}).status_code==409
    assert env.submit(item=item).status_code==409
    assert env.submit(item=item,submitted_at=0).status_code==422

def test_competition_eligibility_hints_and_publication(env):
    aid=env.create_activity('competition',eligible_ids=[env.users['student']],starts_at=now_ms()+100000)
    env.publish(aid);teacher=env.client('teacher');student=env.client();item=env.items(aid)[0]
    assert env.client('other').get('/api/activities/'+aid).status_code==404
    assert student.get('/api/activities/'+aid).json()['items']==[]
    assert env.submit(item=item['id']).status_code==404
    # Release this same problem through another activity; competition must still redact it everywhere.
    for source in env.items(env.assignment):
        teacher.post(f'/api/activities/{env.assignment}/items/{source["id"]}/release',json={'action':'hints'})
        teacher.post(f'/api/activities/{env.assignment}/items/{source["id"]}/release',json={'action':'solution'})
    with env.app.state.sessions() as db:
        db.get(Activity,aid).starts_at=now_ms()-1000;db.commit()
    assert student.get('/api/groups').status_code==403
    assert student.get('/api/groups/'+env.group).status_code==403
    for problem in student.get('/api/problems').json()['items']:
        detail=student.get('/api/problems/'+problem['id']).json();assert detail['hints']=={} and detail['solution']=={}
    assert all(not i['problem']['solution'] and not i['problem']['hints'] for i in student.get('/api/activities/'+env.assignment).json()['items'])
    assert teacher.post(f'/api/activities/{aid}/items/{item["id"]}/release',json={'action':'solution'}).status_code==403
    assert teacher.post('/api/activities/'+aid+'/control',json={'action':'publish_results'}).status_code==409
    sid=env.submit(item=item['id']).json()['id'];assert env.submit(item=item['id'],group_id=env.group,group_revision=1).status_code==403
    env.publish(aid,'end');assert teacher.post('/api/activities/'+aid+'/control',json={'action':'publish_results'}).status_code==409
    assert teacher.put('/api/submissions/'+sid+'/grade',json={'score':7,'version':0,'release':True,'feedback':{'en':'Sealed until publication'}}).status_code==200
    assert student.get('/api/submissions/'+sid).json()['score'] is None
    env.publish(aid,'publish_results');assert student.get('/api/submissions/'+sid).json()['score']==7
    assert student.get('/api/groups').status_code==200

def test_problem_snapshot_and_unicode_search(env):
    teacher=env.client('teacher');pid=env.problems[0];original=teacher.get('/api/problems/'+pid).json();aid=env.create_activity();env.publish(aid)
    allowed=['classroom_id','topic_id','title','statement','subtopic','hints','solution','examples','difficulty','source','year','tags','format','published','version']
    body={k:original[k] for k in allowed};body['title']={'ru':'УНИКАЛЬНАЯ Теорема','en':'Unique theorem'};body['statement']={'en':'Replacement statement'}
    assert teacher.put('/api/problems/'+pid,json=body).status_code==200
    assert teacher.put('/api/problems/'+pid,json=body).status_code==409
    assert teacher.get('/api/proble ms'.replace(' ', '')+'?q=уникальная').json()['total']==1
    assert teacher.get('/api/problems?q=UNIQUE').json()['total']==1
    assert teacher.get('/api/activities/'+aid).json()['items'][0]['problem']['statement']==original['statement']

def test_code_is_stored_never_executed(env,tmp_path):
    teacher=env.client('teacher');room=env.rooms['informatics'];activities=teacher.get('/api/activities?classroom_id='+room).json();assignment=next(a for a in activities if a['kind']=='assignment');item=env.items(assignment['id'])[0]['id']
    marker=tmp_path/'DO_NOT_EXECUTE';code=f'open({str(marker)!r},"w").write("unsafe")'
    response=env.submit(item=item,language='python',content=code)
    assert response.status_code==201 and not marker.exists()
    assert env.client().get('/api/submissions/'+response.json()['id']).json()['content']==code


def test_simultaneous_group_saves_allow_one_version(env):
    from threading import Barrier
    first=env.client();second=env.client('teammate');path='/api/groups/'+env.group+'/document'
    revision=first.get('/api/groups/'+env.group).json()['document']['revision']
    barrier=Barrier(2)
    def save(client,content):
        barrier.wait(timeout=5)
        return client.put(path,json={'content':content,'language':'written','revision':revision})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(save,first,'First concurrent proof'),pool.submit(save,second,'Second concurrent proof')]
        responses=[future.result(timeout=10) for future in futures]
    assert sorted(response.status_code for response in responses)==[200,409]
    saved=first.get('/api/groups/'+env.group).json()['document']
    assert saved['revision']==revision+1
    assert saved['content'] in ('First concurrent proof','Second concurrent proof')
