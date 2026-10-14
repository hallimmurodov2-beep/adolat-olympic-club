from __future__ import annotations
from fastapi import APIRouter, Query, Request
from sqlalchemy import delete, select
from ..errors import require
from ..models import (ExternalAccount, CodeforcesProfile, SubjectMembership, User, now_ms)
from ..schemas_training import AccountInput, RankingConsent, ApprovalInput
from ..security import Actor, Db, throttle
from ..services import codeforces as cf
from ..services import training as training
from ..services.events import audit, notify

router = APIRouter(prefix='/api', tags=['Codeforces — official public API'])


def viewer(db, user):
    if user.role not in ('admin', 'teacher'):
        training.eligible(db, user)


def own(db, user):
    return db.scalar(select(ExternalAccount).where(ExternalAccount.user_id == user.id, ExternalAccount.provider == 'codeforces'))


@router.get('/informatics/codeforces/me')
def me(db: Db, user: Actor):
    account = own(db, user)
    return cf.account_dto(account, db.get(CodeforcesProfile, account.id) if account else None)


@router.put('/integrations/codeforces/account')
def link(body: AccountInput, request: Request, db: Db, user: Actor):
    throttle(db, request.app.state.settings, 'cf-link', user.id, 10, 3600)
    training.eligible(db, user, lock=True)
    account = own(db, user)
    if account and account.normalized_handle == body.handle.casefold():
        data = cf.account_dto(account, db.get(CodeforcesProfile, account.id))
        return data
    if account:
        # Account changes immediately suspend ranking and purge the old profile/evidence.
        from ..models import ExternalObservation
        db.execute(delete(CodeforcesProfile).where(CodeforcesProfile.account_id == account.id))
        db.execute(delete(ExternalObservation).where(ExternalObservation.account_id == account.id))
        account.handle, account.normalized_handle = body.handle, body.handle.casefold()
        account.approval_status, account.approved_handle_key = 'pending_validation', None
        account.approved_by, account.approved_at, account.approval_method = None, None, None
        account.consent_at, account.last_success_at, account.next_refresh_at = now_ms(), None, 0
        account.last_error, account.last_attempt_at = None, None
        account.version += 1
    else:
        account = ExternalAccount(user_id=user.id, handle=body.handle, normalized_handle=body.handle.casefold(), consent_at=now_ms())
        db.add(account)
    db.flush()
    audit(db, user.id, 'codeforces.link_requested', account.id)
    snapshot = (account.id, account.version, account.normalized_handle)
    db.commit()  # Network never holds a request's database transaction.
    cf.refresh_accounts(request.app, [snapshot])
    db.expire_all()
    return me(db, user)


@router.post('/integrations/codeforces/validate')
def validate(request: Request, db: Db, user: Actor):
    training.eligible(db, user)
    account = own(db, user)
    require(account is not None, 'not_found', 404)
    snapshots = [(account.id, account.version, account.normalized_handle)] if account.next_refresh_at <= now_ms() else []
    db.commit()
    cf.refresh_accounts(request.app, snapshots)
    db.expire_all()
    return me(db, user)


@router.delete('/integrations/codeforces/account')
def disconnect(db: Db, user: Actor):
    account = own(db, user)
    if account:
        audit(db, user.id, 'codeforces.disconnected', account.id)
        db.delete(account)  # DB cascades remove cached profile and optional observations.
    return {'ok': True}


@router.post('/integrations/codeforces/leaderboard-consent')
def consent(body: RankingConsent, db: Db, user: Actor):
    if body.opt_in:
        training.eligible(db, user, lock=True)
    account = own(db, user)
    require(account is not None, 'not_found', 404)
    account.leaderboard_opt_in = body.opt_in
    account.version += 1
    audit(db, user.id, 'codeforces.opted_in' if body.opt_in else 'codeforces.opted_out', account.id)
    db.flush()
    return cf.account_dto(account, db.get(CodeforcesProfile, account.id))


@router.get('/informatics/leaderboard')
def leaderboard(request: Request, db: Db, user: Actor, offset: int = Query(0, ge=0, le=10000), limit: int = Query(50, ge=1, le=100)):
    viewer(db, user)
    query = select(ExternalAccount, CodeforcesProfile).join(CodeforcesProfile, CodeforcesProfile.account_id == ExternalAccount.id).join(User, User.id == ExternalAccount.user_id).join(SubjectMembership, (SubjectMembership.user_id == User.id) & (SubjectMembership.subject_id == 'informatics')).where(User.active.is_(True), User.role == 'student', SubjectMembership.active.is_(True), ExternalAccount.leaderboard_opt_in.is_(True), ExternalAccount.approval_status == 'approved')
    # One bounded batch, never an API call per row/browser. All batches share one throttle.
    stale = list(db.execute(query.where(ExternalAccount.next_refresh_at <= now_ms()).order_by(ExternalAccount.next_refresh_at).limit(20)))
    snapshots = [(a.id, a.version, a.normalized_handle) for a, _ in stale]
    db.commit()
    cf.refresh_accounts(request.app, snapshots)
    db.expire_all()
    viewer(db, db.get(User, user.id, populate_existing=True))
    ordered = query.order_by(CodeforcesProfile.rating.desc().nullslast(), CodeforcesProfile.max_rating.desc().nullslast(), ExternalAccount.normalized_handle)
    rows = list(db.execute(ordered.offset(offset).limit(limit + 1)))
    now, ttl = now_ms(), request.app.state.settings.codeforces_profile_ttl_seconds * 1000
    return {'items': [dict(cf.profile_dto(p), position=offset + i + 1 if p.rating is not None else None, school_approved=True,
                          stale=bool(a.last_error) or p.fetched_at + ttl <= now) for i, (a, p) in enumerate(rows[:limit])],
            'next_offset': offset + limit if len(rows) > limit else None, 'server_now': now}


@router.get('/informatics/contests/upcoming')
def contests(request: Request, db: Db, user: Actor):
    viewer(db, user)
    db.commit()
    return cf.upcoming(request.app)


@router.get('/admin/codeforces/approvals')
def approvals(db: Db, user: Actor):
    require(user.role == 'admin')
    return {'items': [dict(cf.account_dto(a, db.get(CodeforcesProfile, a.id)), student_name=u.display_name)
                      for a, u in db.execute(select(ExternalAccount, User).join(User, User.id == ExternalAccount.user_id).order_by(ExternalAccount.created_at).limit(500))]}


@router.post('/admin/codeforces/approvals/{account_id}')
def approval(account_id: str, body: ApprovalInput, request: Request, db: Db, user: Actor):
    require(user.role == 'admin')
    account = db.scalar(select(ExternalAccount).where(ExternalAccount.id == account_id).with_for_update())
    require(account is not None, 'not_found', 404)
    require(account.version == body.version, 'conflict', 409)
    if body.action == 'approve':
        training.eligible(db, db.get(User, account.user_id))
        profile = db.get(CodeforcesProfile, account.id)
        require(account.approval_status == 'pending_approval' and profile is not None and profile.handle.casefold() == account.normalized_handle and profile.fetched_at + request.app.state.settings.codeforces_profile_ttl_seconds * 1000 > now_ms(), 'approval_not_ready', 409)
        duplicate = db.scalar(select(ExternalAccount.id).where(ExternalAccount.approved_handle_key == account.normalized_handle, ExternalAccount.id != account.id))
        require(duplicate is None, 'handle_conflict', 409)
        account.approved_handle_key, account.approval_status = account.normalized_handle, 'approved'
        account.approved_by, account.approved_at, account.approval_method = user.id, now_ms(), body.method
    else:
        account.approval_status = 'rejected' if body.action == 'reject' else 'revoked'
        account.approved_handle_key = None
    account.version += 1
    audit(db, user.id, 'codeforces.' + body.action, account.id, {'method': body.method, 'reason': body.reason, 'version': account.version})
    notify(db, [account.user_id], 'codeforces_reviewed', {}, '/informatics/account')
    db.flush()
    return cf.account_dto(account, db.get(CodeforcesProfile, account.id))
