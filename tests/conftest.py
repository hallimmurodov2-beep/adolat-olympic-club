from __future__ import annotations
import shutil
import os
from uuid import uuid4
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from server.app import create_app
from server.config import Settings
from server.cli import migrate
from server.db import make_engine
from server.models import Activity, ActivityItem, Classroom, Group, Problem, Submission, User
from server.seed import initialize, seed_demo

PASSWORD = 'Test-Only-Passphrase-2026'

@pytest.fixture(scope='session')
def baseline(tmp_path_factory):
    folder = tmp_path_factory.mktemp('baseline')
    settings = Settings(database_url='sqlite:///'+str(folder/'test.db'), data_dir=folder, secret='test-secret-'*5, production=False, origin='http://testserver')
    migrate(settings)
    engine = make_engine(settings)
    with Session(engine) as db:
        initialize(db)
        seed_demo(db, PASSWORD)
        db.commit()
    engine.dispose()
    return folder/'test.db'

class Harness:
    def __init__(self, app):
        self.app=app
        self.clients={}
        with app.state.sessions() as db:
            self.users={u.email.split('@')[0]:u.id for u in db.scalars(select(User))}
            self.rooms={r.subject_id:r.id for r in db.scalars(select(Classroom))}
            self.problems=[p.id for p in db.scalars(select(Problem).where(Problem.classroom_id==self.rooms['math']))]
            self.assignment=db.scalar(select(Activity.id).where(Activity.classroom_id==self.rooms['math'],Activity.kind=='assignment'))
            self.session=db.scalar(select(Activity.id).where(Activity.kind=='session'))
            self.competition=db.scalar(select(Activity.id).where(Activity.kind=='competition'))
            self.item=db.scalar(select(ActivityItem.id).where(ActivityItem.activity_id==self.assignment).order_by(ActivityItem.position))
            self.group=db.scalar(select(Group.id))
    def client(self, handle='student', locale='en'):
        key=(handle,locale)
        if key not in self.clients:
            client=TestClient(self.app)
            response=client.post('/api/auth/login',json={'email':handle+'@demo.school.test','password':PASSWORD,'locale':locale})
            assert response.status_code==200,response.text
            client.headers.update({'X-CSRF-Token':response.json()['csrf'],'X-Locale':locale})
            self.clients[key]=client
        return self.clients[key]
    def create_activity(self,kind='assignment',**kwargs):
        from server.models import now_ms
        data={'classroom_id':self.rooms['math'],'kind':kind,'title':{'ru':'Проверочная работа','en':'Test activity'},'starts_at':now_ms()-1000,'ends_at':now_ms()+3600000,'items':[{'problem_id':self.problems[0],'points':7}]}
        data.update(kwargs)
        response=self.client('teacher').post('/api/activities',json=data)
        assert response.status_code==201,response.text
        return response.json()['id']
    def publish(self,id,action='publish'):
        response=self.client('teacher').post(f'/api/activities/{id}/control',json={'action':action})
        assert response.status_code==200,response.text
        return response.json()
    def items(self,id):
        return self.client('teacher').get('/api/activities/'+id).json()['items']
    def submit(self,item=None,handle='student',**kwargs):
        from uuid import uuid4
        body={'activity_item_id':item or self.item,'content':'My proof: $1+1=2$.','language':'written','client_id':str(uuid4())}
        body.update(kwargs)
        return self.client(handle).post('/api/submissions',json=body)

@pytest.fixture
def env(tmp_path,baseline):
    postgres = os.getenv('TEST_DATABASE_URL')
    operator = None
    if postgres:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import make_url
        if os.getenv('TEST_DATABASE_CONFIRM') != 'disposable' or not (make_url(postgres).database or '').startswith('adolat_test'):
            raise RuntimeError('PostgreSQL tests require an explicitly disposable adolat_test* database; never use a school project.')
        schema = 'test_' + uuid4().hex[:24]
        operator = create_engine(postgres)
        with operator.begin() as conn:
            conn.execute(text('CREATE SCHEMA "' + schema + '"'))
        settings=Settings(database_url=postgres,data_dir=tmp_path,secret='test-secret-'*5,production=False,origin='http://testserver',db_schema=schema)
        migrate(settings)
        seeded=make_engine(settings)
        with Session(seeded) as db:
            initialize(db);seed_demo(db,PASSWORD);db.commit()
        seeded.dispose()
    else:
        shutil.copy2(baseline,tmp_path/'test.db')
        settings=Settings(database_url='sqlite:///'+str(tmp_path/'test.db'),data_dir=tmp_path,secret='test-secret-'*5,production=False,origin='http://testserver')
    app=create_app(settings)
    h=Harness(app)
    yield h
    for client in h.clients.values():client.close()
    app.state.engine.dispose()
    if operator:
        with operator.begin() as conn:
            conn.execute(text('DROP SCHEMA "' + schema + '" CASCADE'))
        operator.dispose()

# One shared fixture definition prevents nested Playwright Sync contexts when
# the retained V1 and new V2 browser modules are collected together.
from tests.browser_harness import BrowserTab, ROOT
import socket, subprocess, threading, time
import uvicorn
from playwright.sync_api import sync_playwright

@pytest.fixture(scope='session')
def chromium():
    subprocess.run(['node',str(ROOT/'scripts/browser-bundle.cjs')],check=True)
    with sync_playwright() as p:
        executable=os.getenv('CHROMIUM_PATH')
        browser=p.chromium.launch(headless=True,**({'executable_path':executable} if executable else {}),args=['--no-sandbox'] if os.getenv('CI') else [])
        yield browser
        browser.close()

@pytest.fixture
def live(env):
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    server=uvicorn.Server(uvicorn.Config(env.app,host='127.0.0.1',port=port,log_level='error',timeout_graceful_shutdown=1))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.02)
    assert server.started
    yield 'http://127.0.0.1:'+str(port)
    server.should_exit=True;thread.join(3)

@pytest.fixture
def tabs(chromium,live):
    opened=[]
    def create(handle=None,locale='ru',viewport=None):
        tab=BrowserTab(chromium,live,viewport);opened.append(tab)
        if handle:tab.login(handle,PASSWORD,locale)
        return tab
    yield create
    for tab in opened:tab.close()
    assert all(not tab.errors for tab in opened),[(tab.errors) for tab in opened if tab.errors]
