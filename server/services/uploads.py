"""Durable upload reservations, exact retries and restart-safe object reconciliation.

All quota/slot changes serialize through the singleton budget. No transaction
remains open while hashing, converting an image, or contacting object storage.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from sqlalchemy import delete, func, select, update
from ..errors import DomainError, require
from ..models import (AuthSession, User, StoredFile, SubmissionFile, ActivityItem, UploadIntent, StorageBudget, now_ms, uid)
from .storage import StorageError, StorageMissing, StorageConflict, LocalStorage
from .leases import acquire, release, insert_ignore
from .events import audit, emit
from .serialize import file_data

PENDING=('reserved','uploading','failed','deleting')


def budget_lock(db):
    used=db.scalar(select(func.coalesce(func.sum(StoredFile.size),0)))
    insert_ignore(db,StorageBudget,{'id':1,'committed_bytes':used,'reserved_bytes':0,'version':1},['id'])
    db.execute(update(StorageBudget).where(StorageBudget.id==1).values(version=StorageBudget.version+1))
    return db.get(StorageBudget,1,populate_existing=True)


def active_actor(db,user_id,session_hash):
    # Explicitly revalidate revocation after upload/network waits.
    actor=db.get(User,user_id,populate_existing=True)
    auth=db.get(AuthSession,session_hash,populate_existing=True)
    require(actor is not None and actor.active and auth is not None and auth.user_id==user_id and auth.expires_at>now_ms(),'unauthenticated',401)
    return actor


def backend_for(app,kind):
    if kind == app.state.settings.storage_backend: return app.state.storage
    # Mixed storage is an operator migration state, never a production disk fallback.
    require(not app.state.settings.production and kind=='local','storage_unavailable',503)
    return LocalStorage(app.state.settings.data_dir/'uploads')


def quota_data(app,user_id):
    with app.state.sessions() as db:
        used=db.scalar(select(func.coalesce(func.sum(StoredFile.size),0)).where(StoredFile.owner_id==user_id))
        reserved=db.scalar(select(func.coalesce(func.sum(UploadIntent.reserved_bytes),0)).where(UploadIntent.owner_id==user_id,UploadIntent.state.in_(PENDING)))
        user=db.get(User,user_id)
        limit=app.state.settings.user_quota_bytes if user.role=='student' else app.state.settings.teacher_quota_bytes
        budget=db.get(StorageBudget,1)
        total=(budget.committed_bytes+budget.reserved_bytes) if budget else db.scalar(select(func.coalesce(func.sum(StoredFile.size),0)))
        return {'used_bytes':used,'reserved_bytes':reserved,'limit_bytes':limit,'file_limit_bytes':app.state.settings.max_upload_bytes,'school_near_limit':total>=app.state.settings.storage_soft_limit_bytes}


def accept_upload(app,user_id,session_hash,kind,target_id,client_id,content,media_type,filename):
    from ..routes.files import target_access, can_read_file
    settings=app.state.settings;checksum=hashlib.sha256(content).hexdigest();size=len(content)
    operation='upload:'+user_id+':'+client_id
    token=acquire(app.state.sessions,operation,ttl_ms=120000)
    require(token is not None,'upload_pending',409)
    intent_id=None
    try:
        with app.state.sessions() as db:
            actor=active_actor(db,user_id,session_hash)
            old=db.scalar(select(UploadIntent).where(UploadIntent.owner_id==user_id,UploadIntent.client_id==client_id))
            if old:
                require((old.target_kind,old.target_id,old.sha256,old.reserved_bytes,old.media_type,old.filename)==(kind,target_id,checksum,size,media_type,filename),'idempotency_mismatch',409)
                if old.state=='ready':
                    file=db.get(StoredFile,old.id);require(file is not None,'not_found',404)
                    can_read_file(db,actor,file);return file_data(file)
                require(old.state not in ('cleaned','deleting'),'upload_expired',409)
            room=target_access(db,actor,kind,target_id,True)
            budget=budget_lock(db)
            if old is None:
                used=db.scalar(select(func.coalesce(func.sum(StoredFile.size),0)).where(StoredFile.owner_id==user_id))
                pending=db.scalar(select(func.coalesce(func.sum(UploadIntent.reserved_bytes),0)).where(UploadIntent.owner_id==user_id,UploadIntent.state.in_(PENDING)))
                limit=settings.user_quota_bytes if actor.role=='student' else settings.teacher_quota_bytes
                require(used+pending+size<=limit,'storage_quota',413)
                require(budget.committed_bytes+budget.reserved_bytes+size<=settings.storage_hard_limit_bytes,'storage_quota',413)
                files_q=select(func.count()).select_from(StoredFile).where(StoredFile.target_kind==kind,StoredFile.target_id==target_id)
                intents_q=select(func.count()).select_from(UploadIntent).where(UploadIntent.target_kind==kind,UploadIntent.target_id==target_id,UploadIntent.state.in_(PENDING))
                if kind=='draft':
                    files_q=files_q.where(StoredFile.owner_id==user_id);intents_q=intents_q.where(UploadIntent.owner_id==user_id)
                require(db.scalar(files_q)+db.scalar(intents_q)<12,'attachment_limit',409)
                identifier=uid()
                old=UploadIntent(id=identifier,owner_id=user_id,client_id=client_id,target_kind=kind,target_id=target_id,classroom_id=room,object_key='files/'+identifier,backend=settings.storage_backend,reserved_bytes=size,sha256=checksum,media_type=media_type,filename=filename,expires_at=now_ms()+86400000)
                db.add(old);budget.reserved_bytes+=size
            old.state='uploading';intent_id=old.id;key=old.object_key;backend=old.backend
            db.commit()
        store=backend_for(app,backend)
        # A lost previous POST response can be reconciled by hashing the existing object.
        info=store.stat(key)
        if info is None:
            try: store.put(key,content,media_type)
            except StorageError:
                info=store.stat(key)
                if info is None: raise
            else: info=store.stat(key)
        require(info is not None and info.size==size and info.sha256==checksum,'storage_unavailable',503)
        with app.state.sessions() as db:
            actor=active_actor(db,user_id,session_hash)
            target_access(db,actor,kind,target_id,True)
            budget=budget_lock(db)
            intent=db.get(UploadIntent,intent_id,populate_existing=True)
            require(intent.state=='uploading','upload_pending',409)
            stored=StoredFile(id=intent.id,owner_id=user_id,classroom_id=intent.classroom_id,target_kind=kind,target_id=target_id,filename=filename,media_type=media_type,size=size,storage_backend=backend,object_key=key,sha256=checksum)
            db.add(stored);db.flush()
            intent.state='ready';budget.reserved_bytes-=size;budget.committed_bytes+=size
            audit(db,user_id,'file.uploaded',stored.id)
            if kind!='draft':emit(db,'group' if kind=='group' else 'library' if kind=='problem' else 'classroom',target_id,classroom_id=intent.classroom_id,group_id=target_id if kind=='group' else None)
            result=file_data(stored);db.commit()
            return result
    except StorageError:
        if intent_id: mark_failed(app,intent_id)
        raise DomainError('storage_unavailable',503)
    except DomainError as exc:
        if intent_id:
            mark_failed(app,intent_id)
            if exc.status in (401,403,404):
                # Revoked parent/identity: no attachment is finalized. Clean on a
                # best-effort basis; durable reservation remains if cleanup fails.
                try: clean_intent(app,intent_id)
                except StorageError: pass
        raise
    finally:
        release(app.state.sessions,operation,token)


def mark_failed(app,intent_id):
    with app.state.sessions() as db:
        # Never turn an already committed result into a failure after response loss.
        if db.get(StoredFile,intent_id) is None:
            db.execute(update(UploadIntent).where(UploadIntent.id==intent_id,UploadIntent.state=='uploading').values(state='failed'))
        db.commit()


def clean_intent(app,intent_id):
    """Caller holds the intent lease, or runs maintenance after the grace period."""
    with app.state.sessions() as db:
        budget_lock(db)
        intent=db.get(UploadIntent,intent_id,populate_existing=True)
        if intent is None or intent.state=='cleaned' or db.get(StoredFile,intent_id) is not None:return False
        intent.state='deleting';key,kind=intent.object_key,intent.backend;db.commit()
    store=backend_for(app,kind);store.delete(key)
    if store.stat(key) is not None:raise StorageError('deletion_unconfirmed')
    with app.state.sessions() as db:
        budget=budget_lock(db);intent=db.get(UploadIntent,intent_id,populate_existing=True)
        if intent.state!='cleaned':
            require(db.get(StoredFile,intent_id) is None,'file_in_use',409)
            budget.reserved_bytes-=intent.reserved_bytes;intent.state='cleaned'
        db.commit()
    return True


def remove_file(app,user_id,session_hash,file_id):
    from ..routes.files import target_access
    with app.state.sessions() as db:
        actor=active_actor(db,user_id,session_hash)
        stored=db.get(StoredFile,file_id);require(stored is not None,'not_found',404)
        target_access(db,actor,stored.target_kind,stored.target_id,True)
        if stored.target_kind=='draft':require(stored.owner_id==user_id,'not_found',404)
        budget=budget_lock(db)
        require(db.scalar(select(SubmissionFile.file_id).where(SubmissionFile.file_id==file_id).limit(1)) is None,'file_in_use',409)
        if stored.target_kind=='problem':require(db.scalar(select(ActivityItem.id).where(ActivityItem.problem_id==stored.target_id).limit(1)) is None,'file_in_use',409)
        intent=db.get(UploadIntent,file_id)
        if intent is None:
            intent=UploadIntent(id=file_id,owner_id=stored.owner_id,client_id=uid(),target_kind=stored.target_kind,target_id=stored.target_id,classroom_id=stored.classroom_id,object_key=stored.object_key or 'files/'+file_id,backend=stored.storage_backend,reserved_bytes=stored.size,sha256=stored.sha256 or '',media_type=stored.media_type,filename=stored.filename,expires_at=now_ms())
            db.add(intent)
        intent.state='deleting';budget.committed_bytes-=stored.size;budget.reserved_bytes+=stored.size
        db.delete(stored);audit(db,user_id,'file.deleted',file_id);db.commit()
    try: clean_intent(app,file_id)
    except StorageError:
        # Detached from mutable work, but bytes stay accounted until confirmed absent.
        return {'ok':True,'cleanup_pending':True}
    return {'ok':True,'cleanup_pending':False}


def reconcile(app,limit=50):
    with app.state.sessions() as db:
        rows=[(r.id,r.owner_id,r.client_id) for r in db.scalars(select(UploadIntent).where(UploadIntent.state.in_(PENDING),UploadIntent.expires_at<now_ms()).order_by(UploadIntent.expires_at).limit(limit))]
    result={'cleaned':0,'failed':0,'busy':0}
    for identifier,owner,client in rows:
        key='upload:'+owner+':'+client;token=acquire(app.state.sessions,key,ttl_ms=120000)
        if token is None:result['busy']+=1;continue
        try:
            if clean_intent(app,identifier):result['cleaned']+=1
        except (StorageError,DomainError):result['failed']+=1
        finally:release(app.state.sessions,key,token)
    return result
