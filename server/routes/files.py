from __future__ import annotations
import io
from pathlib import Path
import re
import warnings
from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask
from urllib.parse import quote
from uuid import UUID, uuid4
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from ..errors import DomainError, require
from ..models import Activity, ActivityItem, Resource, StoredFile, SubmissionFile, uid
from ..security import Actor, Db
from ..services.access import classroom_access, group_access, item_access, lock_open_activity, problem_access, submission_access
from ..services.events import audit, emit
from ..services.resources import admit, UPLOADS
from ..services.serialize import file_data

router = APIRouter(prefix='/api', tags=['Private files'])
Image.MAX_IMAGE_PIXELS = 16_000_000


def target_access(db, user, kind: str, target_id: str, write: bool) -> str:
    if kind == 'problem':
        return problem_access(db, user, target_id, write=write).classroom_id
    if kind == 'resource':
        resource = db.get(Resource, target_id)
        require(resource is not None, 'not_found', 404)
        classroom_access(db, user, resource.classroom_id, write=write)
        return resource.classroom_id
    if kind == 'group':
        group = group_access(db, user, target_id, write=write)
        if write and user.role == 'student':
            item, activity = item_access(db, user, group.activity_item_id, submitting=True)
            lock_open_activity(db, activity)
        return group.classroom_id
    if kind == 'draft':
        require(user.role == 'student', 'forbidden', 403)
        item, activity = item_access(db, user, target_id, submitting=write)
        if write:
            lock_open_activity(db, activity)
        return activity.classroom_id
    raise DomainError('invalid_file', 422)


def can_read_file(db, user, file: StoredFile) -> None:
    # Draft files are personal, even though the target task is shared by a class.
    if file.target_kind != 'draft' or file.owner_id == user.id:
        try:
            target_access(db, user, file.target_kind, file.target_id, False)
            return
        except DomainError:
            pass
    # Once submitted, the immutable attachment is also visible to its reviewers/submitters.
    for submission_id in db.scalars(select(SubmissionFile.submission_id).where(SubmissionFile.file_id == file.id)):
        try:
            submission_access(db, user, submission_id)
            return
        except DomainError:
            continue
    raise DomainError('not_found', 404)


def clean_upload(content: bytes, filename: str, photo: bool = False) -> tuple[bytes, str, str]:
    extension = Path(filename).suffix.casefold()
    safe_name = re.sub(r'[^\w.() \-]', '_', Path(filename.replace('\\', '/')).name, flags=re.UNICODE)[:180].strip('. ') or 'file'
    if extension in ('.png', '.jpg', '.jpeg', '.webp'):
        try:
            with admit(), warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                image = Image.open(io.BytesIO(content))
                require(image.format in ('PNG', 'JPEG', 'WEBP'), 'invalid_file', 422)
                image.load()
                image = ImageOps.exif_transpose(image)
                transparent = 'A' in image.getbands() or 'transparency' in image.info
                image = image.convert('RGBA' if transparent else 'RGB')
                out = io.BytesIO()
                # Strip EXIF (including GPS), metadata and polyglot/trailing bytes.
                if photo and not transparent:
                    # Explicit user choice, no silent pixel downsampling.
                    image.save(out, 'JPEG', quality=90, optimize=True)
                    return out.getvalue(), 'image/jpeg', Path(safe_name).stem[:170] + '.jpg'
                image.save(out, 'PNG', optimize=True)
                return out.getvalue(), 'image/png', Path(safe_name).stem[:170] + '.png'
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise DomainError('invalid_file', 422)
    if extension == '.pdf':
        require(content.startswith(b'%PDF-') and b'%%EOF' in content[-2048:], 'invalid_file', 422)
        return content, 'application/pdf', safe_name
    if extension in ('.txt', '.py', '.cpp'):
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            raise DomainError('invalid_file', 422)
        require('\x00' not in text, 'invalid_file', 422)
        return content, 'text/plain; charset=utf-8', safe_name
    raise DomainError('unsupported_file', 422)


@router.get('/files/quota')
def quota(request: Request, db: Db, user: Actor):
    from ..services.uploads import quota_data
    user_id = user.id
    db.commit()
    return quota_data(request.app, user_id)


@router.post('/files', status_code=201)
async def upload(request: Request, db: Db, user: Actor,
                 target_kind: str = Query(max_length=12),
                 target_id: str = Query(max_length=36),
                 client_id: UUID | None = Query(default=None),
                 photo: bool = Query(default=False), file: UploadFile = File()):
    with admit(UPLOADS):
        # Read permission is a cheap early check. The service performs authoritative
        # write checks before reservation and again after storage I/O. An accepted
        # exact retry may therefore be acknowledged after the writing window closes.
        target_access(db, user, target_kind, target_id, False)
        user_id, session_hash = user.id, request.state.session_hash
        db.commit()  # Do not occupy a pooled connection while reading/converting bytes.
        settings = request.app.state.settings
        buffer = bytearray()
        try:
            while chunk := await file.read(65536):
                buffer.extend(chunk)
                require(len(buffer) <= settings.max_upload_bytes, 'file_too_large', 413)
        finally:
            await file.close()
        require(len(buffer) > 0, 'invalid_file', 422)
        content, media_type, filename = await run_in_threadpool(clean_upload, bytes(buffer), file.filename or '', photo)
        require(len(content) <= settings.max_upload_bytes, 'file_too_large', 413)
        from ..services.uploads import accept_upload
        return await run_in_threadpool(accept_upload, request.app, user_id, session_hash,
                                       target_kind, target_id, str(client_id or uuid4()),
                                       content, media_type, filename)


@router.get('/files/{file_id}')
def download(file_id: str, request: Request, db: Db, user: Actor):
    from ..services.storage import StorageError, StorageMissing
    from ..services.uploads import backend_for
    stored = db.get(StoredFile, file_id)
    require(stored is not None, 'not_found', 404)
    can_read_file(db, user, stored)
    kind, key, filename, media_type, size = (stored.storage_backend, stored.object_key or 'files/' + stored.id,
                                            stored.filename, stored.media_type, stored.size)
    db.commit()
    try:
        reader = backend_for(request.app, kind).open_read(key)
    except StorageMissing:
        raise DomainError('not_found', 404)
    except StorageError:
        raise DomainError('storage_unavailable', 503)
    inline = media_type in ('image/png', 'image/jpeg')
    headers = {'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
               'Content-Security-Policy': "default-src 'none'; sandbox", 'Content-Length': str(size),
               'Content-Disposition': ("inline" if inline else "attachment") + "; filename*=UTF-8''" + quote(filename, safe='')}
    # Iteration is offloaded by StreamingResponse; upstream closes both at EOF
    # and on browser cancellation. Never buffer a cloud file in the ASGI loop.
    return StreamingResponse(iter(reader), media_type=media_type, headers=headers,
                             background=BackgroundTask(reader.close))


@router.delete('/files/{file_id}')
def delete_file(file_id: str, request: Request, db: Db, user: Actor):
    from ..services.uploads import remove_file
    user_id, session_hash = user.id, request.state.session_hash
    db.commit()
    return remove_file(request.app, user_id, session_hash, file_id)
