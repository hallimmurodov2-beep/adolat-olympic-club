"""Opaque, revocable cookie sessions; Argon2id; synchronizer CSRF tokens; durable throttling."""
from __future__ import annotations
import hashlib
import hmac
import secrets
from typing import Annotated
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from .db import get_db
from .config import Settings
from .models import AuthSession, RateLimit, User, now_ms
from .errors import DomainError, require

PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(24))
COOKIE = 'olympiados_session'
Db = Annotated[Session, Depends(get_db)]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password: str) -> str:
    from .services.resources import admit
    with admit():
        return PASSWORDS.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        from .services.resources import admit
        with admit():
            return PASSWORDS.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def csrf_token(settings: Settings, token: str) -> str:
    return hmac.new(settings.secret.encode(), ('csrf:' + token).encode(), hashlib.sha256).hexdigest()


def issue_session(db: Session, response: Response, user: User, settings: Settings) -> str:
    token = secrets.token_urlsafe(48)
    db.add(AuthSession(token_hash=digest(token), user_id=user.id, expires_at=now_ms() + settings.session_seconds * 1000))
    response.set_cookie(COOKIE, token, max_age=settings.session_seconds, httponly=True, secure=settings.production, samesite='strict', path='/')
    return csrf_token(settings, token)


def get_user(request: Request, db: Db) -> User:
    token = request.cookies.get(COOKIE, '')
    session = db.get(AuthSession, digest(token)) if token else None
    require(session is not None and session.expires_at > now_ms(), 'unauthenticated', 401)
    user = db.get(User, session.user_id)
    require(user is not None and user.active, 'unauthenticated', 401)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        supplied = request.headers.get('X-CSRF-Token', '')
        expected = csrf_token(request.app.state.settings, token)
        require(bool(supplied) and hmac.compare_digest(supplied, expected), 'csrf', 403)
    request.state.user = user
    request.state.session_hash = session.token_hash
    return user


Actor = Annotated[User, Depends(get_user)]


def public_user(user: User) -> dict:
    return {'id': user.id, 'display_name': user.display_name, 'email': user.email, 'role': user.role, 'locale': user.locale, 'active': user.active}


def throttle(db: Session, settings: Settings, category: str, identity: str, limit: int, seconds: int = 900) -> None:
    """Atomic database counter works across workers. A rejected attempt still persists."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    key = hmac.new(settings.secret.encode(), (category + ':' + identity).encode(), hashlib.sha256).hexdigest()
    window = (now_ms() // (seconds * 1000)) * seconds
    insert = sqlite_insert if db.bind.dialect.name == 'sqlite' else pg_insert
    query = insert(RateLimit).values(key=key, window=window, count=1)
    query = query.on_conflict_do_update(index_elements=['key', 'window'], set_={'count': RateLimit.count + 1}).returning(RateLimit.count)
    count = db.scalar(query)
    db.commit()
    require(count <= limit, 'rate_limited', 429)
