"""Native HTTP/SSE checks: these tests use no DOM adapter or browser mocking."""
from __future__ import annotations
import json
import socket
import threading
import time
import httpx
import pytest
import uvicorn
from sqlalchemy import func,select
from server.models import Event
from tests.conftest import PASSWORD

@pytest.fixture
def http_server(env):
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    server=uvicorn.Server(uvicorn.Config(env.app,host='127.0.0.1',port=port,log_level='error',timeout_graceful_shutdown=2))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.02)
    assert server.started
    yield f'http://127.0.0.1:{port}'
    server.should_exit=True;thread.join(4)


def messages(response):
    message={'event':'message','data':'','id':''}
    for line in response.iter_lines():
        if not line:
            if message['data']:yield message
            message={'event':'message','data':'','id':''}
        elif ':' in line:
            key,value=line.split(':',1)
            if key in message:message[key]=value.strip()


def test_sse_replay_filters_private_events_and_never_streams_work(env,http_server):
    with env.app.state.sessions() as db:
        cursor=db.scalar(select(func.max(Event.id))) or 0
        db.add(Event(kind='submission',entity_id='private-other',classroom_id=env.rooms['math'],user_id=env.users['teammate']))
        db.add(Event(kind='activity',entity_id='unrelated-room',classroom_id=env.rooms['physics']))
        # The student is actually a physics member; use a private teacher-only
        # recipient there to test scope independently of topic labels.
        db.flush()
        db.query(Event).filter(Event.entity_id=='unrelated-room').update({'user_id':env.users['physics']})
        allowed=Event(kind='activity',entity_id='allowed-item',classroom_id=env.rooms['math'])
        db.add(allowed);db.commit();allowed_id=allowed.id
    with httpx.Client(base_url=http_server,timeout=5) as client:
        auth=client.post('/api/auth/login',json={'email':'student@demo.school.test','password':PASSWORD});assert auth.status_code==200
        for _ in range(2): # Simulate reconnect by replaying exactly the same cursor.
            with client.stream('GET','/api/events',headers={'Last-Event-ID':str(cursor)}) as response:
                assert response.status_code==200
                assert response.headers['content-type'].startswith('text/event-stream')
                received=[]
                for message in messages(response):
                    if message['event']=='change':received.append(message)
                    if message['event']=='heartbeat':break
                assert [json.loads(m['data'])['entity_id'] for m in received]==['allowed-item']
                assert received[0]['id']==str(allowed_id)
                assert set(json.loads(received[0]['data']))=={'kind','entity_id','server_now'}


def test_sse_live_connection_expires_after_logout(env,http_server):
    with httpx.Client(base_url=http_server,timeout=5) as client:
        auth=client.post('/api/auth/login',json={'email':'student@demo.school.test','password':PASSWORD}).json()
        with client.stream('GET','/api/events') as response:
            iterator=messages(response);assert next(iterator)['event']=='ready'
            logout=client.post('/api/auth/logout',json={},headers={'X-CSRF-Token':auth['csrf']});assert logout.status_code==200
            assert any(message['event']=='expired' for message in iterator)
