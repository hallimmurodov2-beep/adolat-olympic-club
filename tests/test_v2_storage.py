"""Byte, authorization, reservation and interruption tests; no cloud credentials."""
from dataclasses import replace
import hashlib
import io
from uuid import uuid4
import httpx
import pytest
from PIL import Image, PngImagePlugin
from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session
from server.models import Activity, Membership, StoredFile, UploadIntent, StorageBudget, now_ms
from server.services.storage import SupabaseStorage, StorageError, StorageConflict
from server.services.uploads import reconcile


def upload(env, key=None, data=b'my proof', handle='student', filename='proof.txt', photo=False):
    path=f'/api/files?target_kind=draft&target_id={env.item}&client_id={key or uuid4()}&photo={str(photo).lower()}'
    return env.client(handle).post(path, files={'file': (filename, data, 'application/octet-stream')})


def budget(env):
    with env.app.state.sessions() as db:
        b=db.get(StorageBudget,1)
        return b.committed_bytes,b.reserved_bytes


def test_upload_exact_retry_hashes_bytes_and_private_streaming(env):
    key=str(uuid4());res=upload(env,key);assert res.status_code==201,res.text
    fid=res.json()['id'];assert upload(env,key).json()['id']==fid
    assert upload(env,key,data=b'a changed request').status_code==409
    received=env.client().get('/api/files/'+fid)
    assert received.content==b'my proof'
    assert received.headers['cache-control']=='private, no-store'
    assert received.headers['content-disposition'].startswith('attachment;')
    assert received.headers['content-security-policy']=="default-src 'none'; sandbox"
    assert env.client('other').get('/api/files/'+fid).status_code==404
    assert budget(env)==(8,0)
    with env.app.state.sessions() as db:
        assert db.get(StoredFile,fid).sha256==hashlib.sha256(b'my proof').hexdigest()
        assert db.get(UploadIntent,fid).state=='ready'
    quota=env.client().get('/api/files/quota').json()
    assert quota['used_bytes']==8 and quota['reserved_bytes']==0
    assert env.client().delete('/api/files/'+fid).status_code==200
    assert budget(env)==(0,0)
    assert env.client().get('/api/files/'+fid).status_code==404


def test_accepted_exact_upload_acknowledges_after_deadline(env):
    key=str(uuid4());r=upload(env,key);assert r.status_code==201
    with env.app.state.sessions() as db:
        db.get(Activity,env.assignment).ends_at=now_ms()-1000;db.commit()
    assert upload(env,key).json()['id']==r.json()['id']
    assert upload(env).status_code==409


def test_cloud_accepted_response_lost_is_reconciled(env,monkeypatch):
    store=env.app.state.storage;original=store.put;calls=[]
    def lost(key,data,media_type):
        calls.append(key);original(key,data,media_type);raise StorageError('synthetic loss after remote success')
    monkeypatch.setattr(store,'put',lost)
    r=upload(env);assert r.status_code==201,r.text
    assert len(calls)==1 and budget(env)==(8,0)


def test_remote_failure_keeps_reservation_and_retry_is_exact(env,monkeypatch):
    store=env.app.state.storage;original=store.put;key=str(uuid4())
    def timeout(*args):raise StorageError('synthetic timeout')
    monkeypatch.setattr(store,'put',timeout)
    r=upload(env,key);assert r.status_code==503,r.text
    assert budget(env)==(0,8)
    with env.app.state.sessions() as db:
        intent=db.scalar(select(UploadIntent).where(UploadIntent.client_id==key))
        assert intent.state=='failed' and db.get(StoredFile,intent.id) is None
    monkeypatch.setattr(store,'put',original)
    assert upload(env,key).status_code==201
    assert budget(env)==(8,0)


def test_revoked_during_object_io_cannot_finalize(env,monkeypatch):
    store=env.app.state.storage;original=store.put
    def revoke(key,data,media_type):
        original(key,data,media_type)
        with env.app.state.sessions() as db:
            # No upload transaction holds a SQLite write lock while this runs.
            db.execute(delete(Membership).where(Membership.classroom_id==env.rooms['math'],Membership.user_id==env.users['student']));db.commit()
    monkeypatch.setattr(store,'put',revoke)
    r=upload(env);assert r.status_code==404,r.text
    assert budget(env)==(0,0)
    with env.app.state.sessions() as db:
        assert list(db.scalars(select(StoredFile)))==[]
        assert db.scalar(select(UploadIntent)).state=='cleaned'
    assert list(store.directory.glob('*'))==[]


def test_corrupt_remote_object_never_gets_committed(env,monkeypatch):
    store=env.app.state.storage;original=store.put
    monkeypatch.setattr(store,'put',lambda key,data,media_type:original(key,b'corrupted',media_type))
    r=upload(env);assert r.status_code==503,r.text
    assert budget(env)==(0,8)
    with env.app.state.sessions() as db:
        assert not list(db.scalars(select(StoredFile)))
        intent=db.scalar(select(UploadIntent));intent.expires_at=0;db.commit()
    assert reconcile(env.app)['cleaned']==1 and budget(env)==(0,0)


def test_lost_final_database_commit_retry_preserves_same_object(env):
    key=str(uuid4());failed=[False]
    def fail_once(session):
        if not failed[0] and any(isinstance(row,StoredFile) for row in session.identity_map.values()) and session.dirty:
            failed[0]=True;raise RuntimeError('synthetic database finalization failure')
    event.listen(Session,'before_commit',fail_once)
    try:
        with pytest.raises(RuntimeError,match='synthetic database'):
            upload(env,key)
    finally:
        event.remove(Session,'before_commit',fail_once)
    assert failed[0] and budget(env)==(0,8)
    r=upload(env,key);assert r.status_code==201,r.text
    assert budget(env)==(8,0)
    with env.app.state.sessions() as db:
        assert len(list(db.scalars(select(StoredFile))))==1
    assert len(list(env.app.state.storage.directory.glob('*')))==1


def test_failed_delete_keeps_bytes_reserved_until_confirmed_absent(env,monkeypatch):
    r=upload(env);fid=r.json()['id'];store=env.app.state.storage;original=store.delete
    def fail(*args):raise StorageError('synthetic deletion failure')
    monkeypatch.setattr(store,'delete',fail)
    r=env.client().delete('/api/files/'+fid);assert r.status_code==200 and r.json()['cleanup_pending']
    assert env.client().get('/api/files/'+fid).status_code==404 and budget(env)==(0,8)
    with env.app.state.sessions() as db:
        db.get(UploadIntent,fid).expires_at=0;db.commit()
    monkeypatch.setattr(store,'delete',original)
    assert reconcile(env.app)['cleaned']==1 and budget(env)==(0,0)
    assert reconcile(env.app)['cleaned']==0


def test_global_budget_applies_across_students_and_release(env):
    env.app.state.settings=replace(env.app.state.settings,storage_hard_limit_bytes=12,storage_soft_limit_bytes=10)
    r=upload(env);assert r.status_code==201
    assert upload(env,handle='teammate').status_code==413
    assert budget(env)==(8,0)
    assert env.client().delete('/api/files/'+r.json()['id']).status_code==200
    assert upload(env,handle='teammate').status_code==201


def test_image_transparency_and_user_selected_photo_format(env):
    buf=io.BytesIO();info=PngImagePlugin.PngInfo();info.add_text('secret','test metadata')
    Image.new('RGBA',(20,20),(0,100,50,128)).save(buf,'PNG',pnginfo=info)
    r=upload(env,data=buf.getvalue(),filename='diagram.png',photo=True);assert r.status_code==201,r.text
    body=env.client().get('/api/files/'+r.json()['id']);assert body.headers['content-type']=='image/png'
    with Image.open(io.BytesIO(body.content)) as image:
        assert image.mode=='RGBA' and 'secret' not in image.info
    buf=io.BytesIO();Image.new('RGB',(40,40),'white').save(buf,'PNG')
    r=upload(env,data=buf.getvalue(),filename='scan.png',photo=True);assert r.status_code==201
    body=env.client().get('/api/files/'+r.json()['id']);assert body.headers['content-type']=='image/jpeg'
    assert body.headers['content-disposition'].startswith('inline')


@pytest.mark.parametrize('secret',['sb_secret_fixture_only','eyJhbGciOiJub25lIn0.fixture.signature'])
def test_supabase_adapter_exact_private_paths_and_key_header(secret):
    objects={};calls=[];fid=str(uuid4());key='files/'+fid
    def request(req):
        calls.append((req.method,req.url.path,dict(req.headers)))
        assert req.url.host=='fixture.supabase.co'
        assert req.headers['apikey']==secret
        if secret.startswith('sb_secret_'):assert 'authorization' not in req.headers
        else:assert req.headers['authorization']=='Bearer '+secret
        assert 'sign' not in req.url.path and 'public' not in req.url.path
        if req.method=='POST':
            assert req.headers['x-upsert']=='false'
            if key in objects:return httpx.Response(409,json={'error':'Duplicate'})
            objects[key]=req.content;return httpx.Response(200,json={'Key':'private/'+key})
        if req.method=='DELETE':objects.pop(key,None);return httpx.Response(200,json={})
        if key not in objects:return httpx.Response(400,json={'statusCode':'404'})
        return httpx.Response(200,content=objects[key])
    store=SupabaseStorage('https://fixture.supabase.co','private',secret,transport=httpx.MockTransport(request))
    assert store.stat(key) is None
    store.put(key,b'original bytes','text/plain')
    with pytest.raises(StorageConflict):store.put(key,b'overwrite forbidden','text/plain')
    assert store.stat(key).sha256==hashlib.sha256(b'original bytes').hexdigest()
    assert b''.join(store.open_read(key))==b'original bytes'
    store.delete(key);assert store.stat(key) is None
    assert any(path=='/storage/v1/object/authenticated/private/'+key for _,path,_ in calls)


def test_supabase_redirect_never_followed_and_keys_not_exfiltrated():
    calls=[]
    def request(req):
        calls.append(req.url.host);return httpx.Response(302,headers={'Location':'https://attacker.invalid/file'})
    store=SupabaseStorage('https://fixture.supabase.co','private','sb_secret_test',transport=httpx.MockTransport(request))
    with pytest.raises(StorageError):store.open_read('files/'+str(uuid4()))
    assert calls==['fixture.supabase.co']
