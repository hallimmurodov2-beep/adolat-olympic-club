from __future__ import annotations
import asyncio
import json
from starlette.concurrency import run_in_threadpool
from sqlalchemy.exc import OperationalError
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from ..models import AuthSession, Classroom, Event, Group, GroupMember, Membership, User, now_ms
from ..security import Actor, Db
from ..errors import DomainError
from ..services.access import classroom_access, classroom_ids, competing, manages, group_access

router = APIRouter(prefix='/api', tags=['Real-time synchronization'])


def event_allowed(db, user: User, event: Event, allowed_rooms: set[str]) -> bool:
    if event.classroom_id and event.classroom_id not in allowed_rooms:
        return False
    room = db.get(Classroom, event.classroom_id) if event.classroom_id else None
    manager = room is not None and manages(user, room)
    if event.group_id:
        try:
            group_access(db, user, event.group_id)
        except DomainError:
            return False
    if event.user_id and event.user_id != user.id and not manager:
        # A group submission event can reach the submitter's teammates, but nobody else.
        if not event.group_id or db.get(GroupMember, (event.group_id, user.id)) is None:
            return False
    return bool(event.classroom_id or event.user_id == user.id)


@router.get('/events')
def events(request: Request, db: Db, user: Actor, classroom_id: str | None = None):
    if classroom_id:
        classroom_access(db, user, classroom_id)
    initial = request.headers.get('Last-Event-ID', request.query_params.get('cursor', ''))
    cursor = int(initial) if initial.isdigit() and len(initial) < 18 else (db.scalar(select(func.max(Event.id))) or 0)
    token_hash = request.state.session_hash
    user_id = user.id
    db.close()  # Do not hold a pooled connection for the lifetime of a stream.

    def snapshot(last_cursor):
        with request.app.state.sessions() as session:
            auth = session.get(AuthSession, token_hash)
            actor = session.get(User, user_id)
            if auth is None or auth.expires_at <= now_ms() or actor is None or not actor.active:
                return 'expired', last_cursor, []
            rooms = set(classroom_ids(session, actor))
            if classroom_id and classroom_id not in rooms:
                return 'expired', last_cursor, []
            candidates, latest, reset = request.app.state.event_feed.read(session, last_cursor)
            if reset:
                return 'reset', latest, []
            messages = []
            for event in candidates:
                last_cursor = event.id
                if classroom_id and event.classroom_id not in (None, classroom_id):
                    continue
                if event_allowed(session, actor, event, rooms):
                    data = {'kind': event.kind, 'entity_id': event.entity_id, 'server_now': now_ms()}
                    messages.append(f'id: {event.id}\nevent: change\ndata: {json.dumps(data)}\n\n')
            return 'ok', last_cursor, messages

    async def stream():
        nonlocal cursor
        yield 'retry: 3000\nevent: ready\nid: ' + str(cursor) + '\ndata: ' + json.dumps({'server_now': now_ms()}) + '\n\n'
        tick = 0
        while not await request.is_disconnected():
            try:
                status, cursor, messages = await run_in_threadpool(snapshot, cursor)
            except OperationalError:
                yield 'event: unavailable\ndata: {}\n\n'
                return
            if status == 'expired':
                yield 'event: expired\ndata: {}\n\n'
                return
            if status == 'reset':
                yield f'id: {cursor}\nevent: reset\ndata: {{}}\n\n'
            for message in messages:
                yield message
            if tick % 10 == 0:
                yield f'id: {cursor}\nevent: heartbeat\ndata: {json.dumps({"server_now": now_ms()})}\n\n'
            tick += 1
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache, no-store', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'})
