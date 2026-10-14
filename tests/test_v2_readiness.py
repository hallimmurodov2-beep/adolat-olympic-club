from dataclasses import replace
from pathlib import Path
from sqlalchemy import text
from server.models import Base, SubjectMembership
from server.services.readiness import check_ready, SCHEMA_REVISION
import pytest


def test_liveness_does_not_require_initialized_database(tmp_path):
    from server.app import create_app
    from server.config import Settings
    from fastapi.testclient import TestClient
    app=create_app(Settings('sqlite:///'+str(tmp_path/'empty.db'),tmp_path,'test-secret-'*5,False,'http://testserver'))
    with TestClient(app) as client:
        assert client.get('/api/health').status_code==200
        assert client.get('/api/ready').status_code==503
    app.state.engine.dispose()


def test_readiness_never_migrates_a_mismatched_database(env):
    assert env.client().get('/api/ready').json()['schema_revision']==SCHEMA_REVISION
    with env.app.state.engine.begin() as conn:conn.execute(text("UPDATE alembic_version SET version_num='wrong_revision'"))
    assert env.client().get('/api/health').status_code==200
    assert env.client().get('/api/ready').status_code==503
    with env.app.state.engine.connect() as conn:assert conn.scalar(text('SELECT version_num FROM alembic_version'))=='wrong_revision'


def test_schema_revision_matches_migrations():
    from alembic.script import ScriptDirectory
    from alembic.config import Config
    assert ScriptDirectory.from_config(Config('alembic.ini')).get_current_head()==SCHEMA_REVISION


@pytest.mark.parametrize('changes',[
    {'production':True},
    {'db_schema':'public'},
    {'db_schema':'bad; DROP SCHEMA public'},
    {'storage_backend':'unknown'},
    {'storage_soft_limit_bytes':900000000,'storage_hard_limit_bytes':100},
    {'codeforces_contest_ttl_seconds':1},
    {'production':True,'database_url':'postgresql+psycopg://user:pass@db.invalid/postgres?sslmode=require'},
])
def test_misconfiguration_fails_closed(env,changes):
    with pytest.raises(ValueError):replace(env.app.state.settings,**changes)


def test_classroom_enrollment_derives_subject_but_does_not_undo_deactivation(env):
    from sqlalchemy import delete
    admin=env.client('admin');student=env.users['other']
    with env.app.state.sessions() as db:
        db.execute(delete(SubjectMembership).where(SubjectMembership.user_id==student,SubjectMembership.subject_id=='informatics'));db.commit()
    assert admin.post('/api/classrooms/'+env.rooms['informatics']+'/members',json={'user_id':student}).status_code==201
    with env.app.state.sessions() as db:
        participation=db.get(SubjectMembership,('informatics',student));assert participation.active
        participation.active=False;db.commit()
    assert admin.post('/api/classrooms/'+env.rooms['informatics']+'/members',json={'user_id':student}).status_code==201
    with env.app.state.sessions() as db:assert not db.get(SubjectMembership,('informatics',student)).active


def test_brand_original_and_browser_metadata(env):
    import hashlib,json
    from fastapi.testclient import TestClient
    from PIL import Image
    root=Path(__file__).resolve().parents[1]
    client=TestClient(env.app);html=client.get('/').text
    assert '<title>Adolat Olympic Club</title>' in html and '∑' not in html
    assert 'favicon.svg' not in html and html.count('name="theme-color"')==1
    assert all('OlympiadOS' not in f.read_text() for f in (root/'frontend').glob('*.ts'))
    assert client.get('/static/manifest.webmanifest').json()['name']=='Adolat Olympic Club'
    for name in ['school-logo-original.png','logo-header.png','logo-header-2x.png','logo-login.png','icon-16.png','icon-32.png','icon-512.png']:
        r=client.get('/static/brand/'+name);assert r.status_code==200
        import io
        image=Image.open(io.BytesIO(r.content));assert image.width>0
    assert hashlib.sha256((root/'static/brand/school-logo-original.png').read_bytes()).hexdigest()==json.loads((root/'static/brand/manifest.json').read_text())['source_sha256']
    client.close()
