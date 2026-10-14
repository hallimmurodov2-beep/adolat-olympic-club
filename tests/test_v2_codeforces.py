"""Deterministic official-API contract, privacy, consent and outage tests."""
from __future__ import annotations
from uuid import uuid4
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update, delete
from server.models import ExternalAccount, CodeforcesProfile, CodeforcesContestCache, OperationLease, SubjectMembership, User, now_ms
from server.services.codeforces import CodeforcesClient, ProviderError, call, refresh_accounts, MAX_BYTES
from tests.test_v2_training import ok, make_cycle, make_plan, make_item


class OfficialFixture:
    def __init__(self):
        self.calls=[];self.error=None;self.users={};self.contests=[]
    def request(self, method, params):
        self.calls.append((method,params))
        if self.error:raise self.error
        if method=='contest.list':return self.contests
        assert method=='user.info' and params['checkHistoricHandles']=='false'
        return [self.users.get(h,{'handle':h,'rating':1400,'maxRating':1500,'rank':'specialist','registrationTimeSeconds':100}) for h in params['handles'].split(';')]


@pytest.fixture
def provider(env):
    fixture=OfficialFixture();env.app.state.codeforces=fixture
    return fixture


def reset_reservations(env):
    with env.app.state.sessions() as db:
        db.execute(delete(OperationLease));db.commit()


def link(env, who='student', handle='AdolatStudent'):
    return ok(env.client(who).put('/api/integrations/codeforces/account',json={'handle':handle,'consent':True}))


def approve(env, who='student'):
    state=ok(env.client(who).get('/api/informatics/codeforces/me'));a=state['account']
    return ok(env.client('admin').post('/api/admin/codeforces/approvals/'+a['id'],json={'action':'approve','method':'observed_login','version':a['version']}))


def opt(env, who='student', value=True):
    return ok(env.client(who).post('/api/integrations/codeforces/leaderboard-consent',json={'opt_in':value}))


def test_link_validation_is_not_ownership_and_ranking_requires_separate_opt_in(env,provider):
    student=env.client();state=link(env)
    assert state['state']=='pending_approval'
    assert not state['account']['leaderboard_opt_in']
    assert state['account']['profile']['rating']==1400
    assert ok(student.get('/api/informatics/leaderboard'))['items']==[]
    approve(env)
    assert ok(student.get('/api/informatics/codeforces/me'))['state']=='approved_not_opted_in'
    assert ok(student.get('/api/informatics/leaderboard'))['items']==[]
    opt(env)
    rows=ok(student.get('/api/informatics/leaderboard'))['items']
    assert len(rows)==1
    assert rows[0]['handle']=='adolatstudent' and rows[0]['rating']==1400 and rows[0]['max_rating']==1500
    assert rows[0]['rank']=='specialist' and rows[0]['last_updated_at']>0 and rows[0]['school_approved']
    assert all(k not in str(rows) for k in ('email','user_id','password','consent_at'))
    assert len(provider.calls)==1  # All cached reads share one snapshot.
    opt(env,value=False)
    assert ok(student.get('/api/informatics/leaderboard'))['items']==[]


def test_consent_validation_auth_and_staff_approval_boundaries(env,provider):
    assert TestClient(env.app).get('/api/informatics/leaderboard').status_code==401
    assert env.client('other').get('/api/informatics/leaderboard').status_code==403
    student=env.client()
    for data in ({'handle':'safe'}, {'handle':'safe','consent':False}, {'handle':'../evil','consent':True}, {'handle':'safe','consent':True,'password':'forbidden'}):
        assert student.put('/api/integrations/codeforces/account',json=data).status_code==422
    a=link(env)['account'];payload={'action':'approve','method':'observed_login','version':a['version']}
    for who in ('student','teammate','teacher'):
        assert env.client(who).post('/api/admin/codeforces/approvals/'+a['id'],json=payload).status_code==403
        assert env.client(who).get('/api/admin/codeforces/approvals').status_code==403
    assert env.client('admin').post('/api/admin/codeforces/approvals/'+a['id'],json={'action':'approve','version':a['version']}).status_code==422
    assert env.client('admin').post('/api/admin/codeforces/approvals/'+a['id'],json={**payload,'version':999}).status_code==409


def test_handle_change_requires_reapproval_and_disconnect_preserves_training(env,provider):
    cycle,_=make_cycle(env);plan=make_plan(env,cycle['id']);make_item(env,plan['id'])
    link(env);approve(env);opt(env);reset_reservations(env)
    changed=link(env,handle='AnotherHandle')
    assert changed['state']=='pending_approval'
    assert ok(env.client().get('/api/informatics/leaderboard'))['items']==[]
    approve(env)
    assert len(ok(env.client().get('/api/informatics/leaderboard'))['items'])==1
    ok(env.client().delete('/api/integrations/codeforces/account'))
    assert ok(env.client().get('/api/informatics/codeforces/me'))['state']=='not_connected'
    assert ok(env.client().get('/api/training/plans/'+plan['id']))['items']
    with env.app.state.sessions() as db:
        assert not list(db.scalars(select(ExternalAccount)))
        assert not list(db.scalars(select(CodeforcesProfile)))


def test_approved_canonical_handle_unique_but_pending_claims_do_not_squat(env,provider):
    link(env,handle='CanonicalHandle');reset_reservations(env)
    duplicate=link(env,'teammate',handle='canonicalhandle');opt(env,'teammate')
    approve(env)
    account=duplicate['account']
    # Opt-in changed its version; retrieve the current one.
    account=ok(env.client('teammate').get('/api/informatics/codeforces/me'))['account']
    response=env.client('admin').post('/api/admin/codeforces/approvals/'+account['id'],json={'action':'approve','method':'observed_login','version':account['version']})
    assert response.status_code==409 and response.json()['error']['code']=='handle_conflict'
    assert ok(env.client().get('/api/informatics/leaderboard'))['items']==[]


def test_unrated_missing_fields_are_not_fabricated(env,provider):
    provider.users['newaccount']={'handle':'NewAccount'}
    state=link(env,handle='NewAccount');approve(env);opt(env)
    row=ok(env.client().get('/api/informatics/leaderboard'))['items'][0]
    assert row['rating'] is None and row['max_rating'] is None and row['rank'] is None and row['position'] is None


def test_rating_order_max_ties_and_unrated_last(env,provider):
    # Only synthetic school-approved fixtures; no real accounts are claimed.
    t=now_ms()
    with env.app.state.sessions() as db:
        template=db.get(User,env.users['student'])
        for n,(handle,rating,max_rating) in enumerate([('Zeta',1500,1700),('Alpha',1500,1700),('Beta',1500,1800),('Master',2000,2100),('Newbie',None,None)]):
            u=User(email=f'cf-fixture-{n}@example.test',display_name='Test pupil',password_hash=template.password_hash,role='student')
            db.add(u);db.flush();db.add(SubjectMembership(subject_id='informatics',user_id=u.id))
            a=ExternalAccount(user_id=u.id,handle=handle,normalized_handle=handle.lower(),consent_at=t,leaderboard_opt_in=True,approval_status='approved',approved_handle_key=handle.lower(),approved_by=env.users['admin'],approved_at=t,approval_method='observed_login',next_refresh_at=t+9999999)
            db.add(a);db.flush();db.add(CodeforcesProfile(account_id=a.id,handle=handle,rating=rating,max_rating=max_rating,fetched_at=t))
        db.commit()
    page=ok(env.client().get('/api/informatics/leaderboard',params={'limit':2}))
    assert [r['handle'] for r in page['items']]==['Master','Beta']
    page2=ok(env.client().get('/api/informatics/leaderboard',params={'offset':page['next_offset'],'limit':100}))
    assert [r['handle'] for r in page2['items']]==['Alpha','Zeta','Newbie']
    assert page2['items'][-1]['position'] is None
    assert not provider.calls


@pytest.mark.parametrize('code',['provider_unavailable','provider_rate_limited','provider_invalid'])
def test_outage_preserves_approval_consent_cached_rating_and_private_training(env,provider,code):
    link(env);approve(env);opt(env);reset_reservations(env)
    with env.app.state.sessions() as db:
        a=db.scalar(select(ExternalAccount));a.next_refresh_at=0;db.commit()
    provider.error=ProviderError(code)
    rows=ok(env.client().get('/api/informatics/leaderboard'))['items']
    assert len(rows)==1 and rows[0]['rating']==1400 and rows[0]['stale']
    state=ok(env.client().get('/api/informatics/codeforces/me'))
    assert state['state']=='approved_opted_in' and state['account']['last_error']==code
    cycle,_=make_cycle(env);assert make_plan(env,cycle['id'])['id']


def test_unknown_handle_is_not_provider_outage(env,provider):
    provider.error=ProviderError('invalid_handle','missinghandle')
    state=link(env,handle='MissingHandle')
    assert state['state']=='invalid_handle' and state['account']['profile'] is None
    assert ok(env.client().get('/api/informatics/leaderboard'))['items']==[]


def test_alias_or_registration_identity_change_suspends_approval(env,provider):
    link(env);approve(env);opt(env);reset_reservations(env)
    provider.users['adolatstudent']={'handle':'RenamedHandle','rating':3000,'maxRating':3000}
    with env.app.state.sessions() as db:
        a=db.scalar(select(ExternalAccount));a.next_refresh_at=0;db.commit()
    assert ok(env.client().get('/api/informatics/leaderboard'))['items']==[]
    state=ok(env.client().get('/api/informatics/codeforces/me'))
    assert state['state']=='pending_validation' and state['account']['last_error']=='handle_changed'


def test_delayed_profile_response_cannot_restore_disconnected_or_changed_link(env,provider):
    original=link(env)['account']
    snap=(original['id'],original['version'],'adolatstudent')
    reset_reservations(env)
    ok(env.client().delete('/api/integrations/codeforces/account'))
    refresh_accounts(env.app,[snap])
    assert ok(env.client().get('/api/informatics/codeforces/me'))['state']=='not_connected'


def test_deactivation_and_revocation_remove_rows_immediately(env,provider):
    link(env);approve(env);opt(env)
    admin=env.client('admin');account=ok(env.client().get('/api/informatics/codeforces/me'))['account']
    ok(admin.post('/api/admin/codeforces/approvals/'+account['id'],json={'action':'revoke','version':account['version'],'reason':'Ownership needs review'}))
    assert ok(env.client().get('/api/informatics/leaderboard'))['items']==[]


def test_upcoming_contests_filter_sort_cache_duration_and_outage(env,provider):
    now=now_ms()//1000
    provider.contests=[{'id':n,'name':f'Fixture contest {n}','phase':'BEFORE','startTimeSeconds':now+offset,'durationSeconds':7200} for n,offset in [(3,4000),(1,1000),(2,2000)]]
    provider.contests += [{'id':4,'name':'Already ended','phase':'FINISHED','startTimeSeconds':now-5000,'durationSeconds':500}, {'id':5,'name':'Past stale before','phase':'BEFORE','startTimeSeconds':now-5,'durationSeconds':500}, {'id':6,'name':'Date not set','phase':'BEFORE'}]
    result=ok(env.client().get('/api/informatics/contests/upcoming'))
    assert [c['id'] for c in result['items']]==[1,2,3]
    assert result['items'][0]['duration_seconds']==7200 and result['items'][0]['url']=='https://codeforces.com/contest/1'
    assert not result['stale'] and result['last_updated_at']
    ok(env.client('teammate').get('/api/informatics/contests/upcoming'));assert len(provider.calls)==1
    with env.app.state.sessions() as db:
        db.get(CodeforcesContestCache,1).next_refresh_at=0;db.commit()
    reset_reservations(env);provider.error=ProviderError('provider_unavailable')
    stale=ok(env.client().get('/api/informatics/contests/upcoming'))
    assert stale['stale'] and stale['items']==result['items'] and stale['last_updated_at']==result['last_updated_at']


def test_empty_cache_unavailable_and_empty_success_distinct(env,provider):
    provider.error=ProviderError('provider_unavailable')
    r=ok(env.client().get('/api/informatics/contests/upcoming'))
    assert not r['available'] and r['items']==[] and r['stale'] and r['source_url']=='https://codeforces.com/contests'
    reset_reservations(env);provider.error=None
    with env.app.state.sessions() as db:db.get(CodeforcesContestCache,1).next_refresh_at=0;db.commit()
    success=ok(env.client().get('/api/informatics/contests/upcoming'))
    assert success['available'] and not success['stale'] and success['items']==[]


def test_shared_aggregate_throttle_across_profiles_and_contests(env,provider):
    link(env)
    r=ok(env.client().get('/api/informatics/contests/upcoming'))
    assert r['error']=='provider_busy' and len(provider.calls)==1
    with env.app.state.sessions() as db:
        lease=db.get(OperationLease,'codeforces:global')
        assert lease.not_before>now_ms() and lease.expires_at==0


def test_concurrent_provider_requests_allow_one_transport_call(env,provider):
    barrier=Barrier(2)
    def run(n):
        barrier.wait(timeout=5)
        try:return call(env.app,'operation'+str(n),'contest.list',{'gym':'false'})
        except ProviderError as exc:return exc.code
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(run,[1,2]))
    assert results.count('provider_busy')==1 and len(provider.calls)==1


@pytest.mark.parametrize('status,payload,code',[
    (429,{},'provider_rate_limited'),(503,{},'provider_unavailable'),
    (302,{},'provider_unavailable'),(200,{'status':'FAILED','comment':'Call limit exceeded'},'provider_rate_limited'),
    (200,{'status':'FAILED','comment':'handles: User with handle missing not found'},'invalid_handle'),
    (200,{'status':'OK','result':{}},'provider_invalid'),(200,[],'provider_invalid')])
def test_http_adapter_envelope_and_failure_contract(status,payload,code):
    seen=[]
    def transport(request):
        seen.append(request)
        return httpx.Response(status,json=payload)
    client=CodeforcesClient(httpx.MockTransport(transport))
    with pytest.raises(ProviderError) as exc:client.request('user.info',{'handles':'missing'})
    assert exc.value.code==code
    assert seen[0].url.host=='codeforces.com' and seen[0].url.path=='/api/user.info'
    assert 'authorization' not in seen[0].headers


def test_http_adapter_timeout_malformed_and_bounded_size():
    def timeout(request):raise httpx.ReadTimeout('fixture',request=request)
    for transport in (httpx.MockTransport(timeout),httpx.MockTransport(lambda r:httpx.Response(200,content=b'not json')),httpx.MockTransport(lambda r:httpx.Response(200,content=b'x'*(MAX_BYTES+1)))):
        with pytest.raises(ProviderError):CodeforcesClient(transport).request('contest.list',{'gym':'false'})
    with pytest.raises(ProviderError):CodeforcesClient().request('https://example.com',{})
