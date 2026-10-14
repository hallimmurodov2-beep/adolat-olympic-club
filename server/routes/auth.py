from __future__ import annotations
import secrets
from fastapi import APIRouter, Request, Response
from sqlalchemy import delete, select, update
from ..errors import DomainError, require
from ..models import AuthSession, Classroom, ClubSettings, Invitation, EnrollmentInvitation, Membership, User, now_ms
from ..schemas import ActiveInput, InviteInput, LoginInput, PasswordInput, ProfileInput, RegisterInput, InvitationTokenInput
from ..security import Actor, COOKIE, Db, DUMMY_HASH, csrf_token, digest, hash_password, issue_session, public_user, throttle, verify_password
from ..services.access import classroom_access
from ..services.events import audit, emit

router = APIRouter(prefix='/api', tags=['Authentication and administration'])


def settings_data(db) -> dict:
    settings = db.get(ClubSettings, 1)
    return {'name': settings.name, 'timezone': settings.timezone}


@router.post('/auth/login')
def login(body: LoginInput, request: Request, response: Response, db: Db):
    email = body.email.strip().casefold()
    settings = request.app.state.settings
    throttle(db, settings, 'login-ip', request.client.host, 100)
    throttle(db, settings, 'login-email', email, 12)
    user = db.scalar(select(User).where(User.email == email))
    user_id, encoded = (user.id, user.password_hash) if user else (None, DUMMY_HASH)
    db.commit()  # Release the pooled connection during expensive verification.
    valid = verify_password(body.password, encoded)
    require(valid and user_id is not None, 'invalid_credentials', 401)
    guard = db.execute(update(User).where(User.id == user_id, User.password_hash == encoded, User.active.is_(True)).values(active=User.active).execution_options(synchronize_session=False))
    require(guard.rowcount == 1, 'invalid_credentials', 401)
    user = db.get(User, user_id, populate_existing=True)
    if body.locale:
        user.locale = body.locale
    # Re-authentication rotates, rather than accumulating, this browser's session.
    previous = request.cookies.get(COOKIE)
    if previous:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == digest(previous)))
    csrf = issue_session(db, response, user, settings)
    audit(db, user.id, 'auth.login', user.id)
    return {'user': public_user(user), 'csrf': csrf, 'settings': settings_data(db), 'server_now': now_ms()}


@router.get('/auth/me')
def me(request: Request, db: Db, user: Actor):
    return {'user': public_user(user), 'csrf': csrf_token(request.app.state.settings, request.cookies[COOKIE]), 'settings': settings_data(db), 'server_now': now_ms()}


@router.post('/auth/logout')
def logout(request: Request, response: Response, db: Db, user: Actor):
    db.execute(delete(AuthSession).where(AuthSession.token_hash == request.state.session_hash))
    response.delete_cookie(COOKIE, path='/', secure=request.app.state.settings.production, httponly=True, samesite='strict')
    return {'ok': True}


@router.post('/auth/invitation')
def invitation_info(body: InvitationTokenInput, db: Db):
    token = body.token
    require(30 <= len(token) <= 128, 'invalid_invitation', 404)
    invite = db.scalar(select(Invitation).where(Invitation.token_hash == digest(token), Invitation.accepted_at.is_(None), Invitation.expires_at > now_ms()))
    require(invite is not None, 'invalid_invitation', 404)
    room = db.get(Classroom, invite.classroom_id) if invite.classroom_id else None
    return {'email': invite.email, 'role': invite.role, 'classroom_name': room.name if room else {}, 'expires_at': invite.expires_at}


@router.post('/auth/register', status_code=201)
def register(body: RegisterInput, request: Request, response: Response, db: Db):
    throttle(db, request.app.state.settings, 'register-ip', request.client.host, 30)
    invite = db.scalar(select(Invitation).where(Invitation.token_hash == digest(body.token)))
    require(invite is not None and invite.accepted_at is None and invite.expires_at > now_ms(), 'invalid_invitation', 400)
    require(db.scalar(select(User.id).where(User.email == invite.email)) is None, 'account_exists', 409)
    require(bool(body.display_name.strip()), 'invalid_input', 422)
    db.commit()  # The invitation CAS below rechecks expiry/revocation after hashing.
    encoded = hash_password(body.password)
    # Compare-and-swap consumes exactly once even with concurrent registrations.
    consumed = db.execute(update(Invitation).where(Invitation.id == invite.id, Invitation.accepted_at.is_(None), Invitation.expires_at > now_ms()).values(accepted_at=now_ms()))
    require(consumed.rowcount == 1, 'invalid_invitation', 409)
    user = User(email=invite.email, display_name=body.display_name.strip(), password_hash=encoded, role=invite.role, locale=body.locale)
    db.add(user)
    db.flush()
    if invite.classroom_id:
        db.add(Membership(classroom_id=invite.classroom_id, user_id=user.id))
        from ..services.training import ensure_subject_participation
        ensure_subject_participation(db, db.get(Classroom, invite.classroom_id).subject_id, user.id)
        emit(db, 'membership', invite.classroom_id, classroom_id=invite.classroom_id)
    csrf = issue_session(db, response, user, request.app.state.settings)
    audit(db, user.id, 'auth.register', user.id)
    return {'user': public_user(user), 'csrf': csrf, 'settings': settings_data(db), 'server_now': now_ms()}


@router.patch('/profile')
def profile(body: ProfileInput, db: Db, user: Actor):
    if body.display_name is not None:
        require(bool(body.display_name.strip()), 'invalid_input', 422)
        user.display_name = body.display_name.strip()
    if body.locale is not None:
        user.locale = body.locale
    emit(db, 'profile', user.id, user_id=user.id)
    return public_user(user)


@router.post('/auth/password')
def change_password(body: PasswordInput, request: Request, response: Response, db: Db, user: Actor):
    throttle(db, request.app.state.settings, 'password-change', user.id, 6)
    require(verify_password(body.current_password, user.password_hash), 'invalid_credentials', 401)
    user.password_hash = hash_password(body.new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    csrf = issue_session(db, response, user, request.app.state.settings)
    audit(db, user.id, 'auth.password_changed', user.id)
    return {'csrf': csrf}


@router.get('/admin/users')
def users(db: Db, user: Actor):
    require(user.role == 'admin')
    return [public_user(u) for u in db.scalars(select(User).order_by(User.created_at).limit(2000))]


@router.patch('/admin/users/{user_id}')
def set_active(user_id: str, body: ActiveInput, db: Db, user: Actor):
    require(user.role == 'admin')
    target = db.get(User, user_id)
    require(target is not None, 'not_found', 404)
    require(user_id != user.id, 'cannot_disable_self', 409)
    # Runtime roles cannot be changed through this or any other profile API.
    target.active = body.active
    if not body.active:
        db.execute(delete(AuthSession).where(AuthSession.user_id == target.id))
    audit(db, user.id, 'user.activated' if body.active else 'user.deactivated', target.id)
    return public_user(target)


@router.get('/invitations')
def invitations(db: Db, user: Actor):
    require(user.role in ('admin', 'teacher'))
    query = select(Invitation).order_by(Invitation.expires_at.desc()).limit(100)
    if user.role == 'teacher':
        query = query.where(Invitation.created_by == user.id)
    records = [{'id': i.id, 'email': i.email, 'role': i.role, 'classroom_id': i.classroom_id, 'expires_at': i.expires_at, 'accepted_at': i.accepted_at, 'kind': 'registration'} for i in db.scalars(query)]
    enrollment_query = select(EnrollmentInvitation, User.email).join(User, EnrollmentInvitation.user_id == User.id).order_by(EnrollmentInvitation.created_at.desc()).limit(100)
    if user.role == 'teacher':
        enrollment_query = enrollment_query.where(EnrollmentInvitation.created_by == user.id)
    records.extend({'id': i.id, 'email': email, 'role': 'student', 'classroom_id': i.classroom_id,
                    'expires_at': i.expires_at, 'accepted_at': i.accepted_at, 'kind': 'existing_account'}
                   for i, email in db.execute(enrollment_query))
    return sorted(records, key=lambda r: r['expires_at'], reverse=True)[:100]


@router.post('/invitations', status_code=201)
def invite(body: InviteInput, request: Request, db: Db, user: Actor):
    require(user.role in ('admin', 'teacher'))
    if user.role == 'teacher':
        require(body.role == 'student' and body.classroom_id is not None)
    if body.classroom_id:
        classroom_access(db, user, body.classroom_id, write=True)
        require(body.role == 'student', 'invalid_input', 422)
    existing_account = db.scalar(select(User).where(User.email == body.email))
    require(existing_account is None or (body.role == 'student' and body.classroom_id is not None and existing_account.active and existing_account.role == 'student'), 'account_exists', 409)
    throttle(db, request.app.state.settings, 'invite', user.id, 60, 3600)
    if existing_account:
        room = classroom_access(db, user, body.classroom_id, write=True)
        require(room.active, 'classroom_archived', 409)
        require(db.get(Membership, (room.id, existing_account.id)) is None, 'already_member', 409)
        # Revoke prior unaccepted links to this same school account/classroom.
        db.execute(update(EnrollmentInvitation).where(EnrollmentInvitation.classroom_id == room.id,
            EnrollmentInvitation.user_id == existing_account.id, EnrollmentInvitation.accepted_at.is_(None)).values(expires_at=now_ms()))
        token = secrets.token_urlsafe(36)
        enrollment = EnrollmentInvitation(token_hash=digest(token), classroom_id=room.id,
            user_id=existing_account.id, created_by=user.id, expires_at=now_ms() + 7 * 86400000)
        db.add(enrollment)
        db.flush()
        audit(db, user.id, 'enrollment_invitation.created', enrollment.id)
        return {'id': enrollment.id, 'kind': 'existing_account',
                'link': request.app.state.settings.origin + '/#/enroll/' + token, 'expires_at': enrollment.expires_at}

    token = secrets.token_urlsafe(36)
    db.execute(update(Invitation).where(Invitation.email == body.email, Invitation.accepted_at.is_(None)).values(expires_at=now_ms()))
    invitation = Invitation(token_hash=digest(token), email=body.email, role=body.role, classroom_id=body.classroom_id, created_by=user.id, expires_at=now_ms() + 7 * 86400000)
    db.add(invitation)
    db.flush()
    audit(db, user.id, 'invitation.created', invitation.id)
    return {'id': invitation.id, 'link': request.app.state.settings.origin + '/#/register/' + token, 'expires_at': invitation.expires_at}


@router.delete('/enrollment-invitations/{invitation_id}')
def revoke_enrollment_invitation(invitation_id: str, db: Db, user: Actor):
    invite = db.get(EnrollmentInvitation, invitation_id)
    require(invite is not None, 'not_found', 404)
    require(user.role == 'admin' or (user.role == 'teacher' and invite.created_by == user.id))
    invite.expires_at = now_ms()
    audit(db, user.id, 'enrollment_invitation.revoked', invite.id)
    return {'ok': True}


@router.delete('/invitations/{invitation_id}')
def revoke_invitation(invitation_id: str, db: Db, user: Actor):
    invitation = db.get(Invitation, invitation_id)
    require(invitation is not None, 'not_found', 404)
    require(user.role == 'admin' or (user.role == 'teacher' and invitation.created_by == user.id))
    invitation.expires_at = now_ms()
    audit(db, user.id, 'invitation.revoked', invitation.id)
    return {'ok': True}


@router.post('/auth/enrollment-preview')
def enrollment_preview(body: InvitationTokenInput, db: Db, user: Actor):
    invite = db.scalar(select(EnrollmentInvitation).where(
        EnrollmentInvitation.token_hash == digest(body.token),
        EnrollmentInvitation.accepted_at.is_(None), EnrollmentInvitation.expires_at > now_ms()))
    require(invite is not None and invite.user_id == user.id, 'invalid_invitation', 404)
    room = db.get(Classroom, invite.classroom_id)
    require(room is not None and room.active and user.role == 'student', 'invalid_invitation', 404)
    return {'classroom_name': room.name, 'expires_at': invite.expires_at}


@router.post('/auth/enroll')
def accept_enrollment(body: InvitationTokenInput, db: Db, user: Actor):
    # A token cannot change the target account or confer teacher/admin status.
    invite = db.scalar(select(EnrollmentInvitation).where(EnrollmentInvitation.token_hash == digest(body.token)))
    require(invite is not None and invite.user_id == user.id and user.role == 'student', 'invalid_invitation', 404)
    # Serialize with classroom offboarding and duplicate redemption on PostgreSQL.
    room = db.scalar(select(Classroom).where(Classroom.id == invite.classroom_id).with_for_update())
    require(room is not None and room.active, 'invalid_invitation', 404)
    consumed = db.execute(update(EnrollmentInvitation).where(EnrollmentInvitation.id == invite.id,
        EnrollmentInvitation.accepted_at.is_(None), EnrollmentInvitation.expires_at > now_ms()).values(accepted_at=now_ms()))
    require(consumed.rowcount == 1, 'invalid_invitation', 409)
    require(db.get(Membership, (room.id, user.id)) is None, 'already_member', 409)
    db.add(Membership(classroom_id=room.id, user_id=user.id))
    from ..services.training import ensure_subject_participation
    ensure_subject_participation(db, room.subject_id, user.id)
    audit(db, user.id, 'enrollment_invitation.accepted', invite.id)
    emit(db, 'membership', room.id, classroom_id=room.id)
    return {'ok': True, 'classroom_id': room.id}
