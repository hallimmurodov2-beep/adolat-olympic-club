"""Official public API only. No keys, scraping, sources, arbitrary URLs or browser polling.

Contract sources: https://codeforces.com/apiHelp{,/methods,/objects}
Checked 2026-10-14. Public user.info and contest.list; a conservative 3s shared
reservation plus in-flight exclusion covers every method, including optional F11.
"""
from __future__ import annotations
import json
import re
import time
from urllib.parse import quote
import httpx
from sqlalchemy import select
from ..models import (ExternalAccount, CodeforcesProfile, CodeforcesContestCache, SubjectMembership,
                      User, TrainingItem, TrainingPlan, ExternalObservation, now_ms)
from .leases import acquire, release, insert_ignore

HANDLE = re.compile(r'[A-Za-z0-9_.-]{3,24}\Z')
MAX_BYTES = 4 * 1024 * 1024


class ProviderError(Exception):
    def __init__(self, code, handle=None):
        self.code, self.handle = code, handle
        super().__init__(code)


class CodeforcesClient:
    def __init__(self, transport=None):
        self.transport = transport

    def request(self, method, params):
        if method not in ('user.info', 'contest.list', 'user.status'):
            raise ProviderError('provider_invalid')
        try:
            deadline = time.monotonic() + 12.0
            # Fixed host, no redirects (including bot challenges); bounded response.
            with httpx.Client(timeout=httpx.Timeout(7.0, connect=3.0), follow_redirects=False, transport=self.transport,
                              headers={'User-Agent': 'AdolatOlympicClub/2.0 (school training, public API)'}) as client:
                with client.stream('GET', 'https://codeforces.com/api/' + method, params=params) as response:
                    if response.status_code != 200:
                        raise ProviderError('provider_rate_limited' if response.status_code == 429 else 'provider_unavailable')
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() > deadline:
                            raise ProviderError('provider_unavailable')
                        content.extend(chunk)
                        if len(content) > MAX_BYTES:
                            raise ProviderError('provider_invalid')
            if time.monotonic() > deadline:
                raise ProviderError('provider_unavailable')
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ProviderError('provider_invalid')
            if data.get('status') == 'FAILED':
                comment = data.get('comment', '')
                if not isinstance(comment, str):
                    raise ProviderError('provider_invalid')
                match = re.search(r'User with handle ([A-Za-z0-9_.-]{3,24}) not found', comment, re.I)
                if match:
                    raise ProviderError('invalid_handle', match[1].casefold())
                raise ProviderError('provider_rate_limited' if 'limit' in comment.casefold() else 'provider_unavailable')
            if data.get('status') != 'OK' or not isinstance(data.get('result'), list):
                raise ProviderError('provider_invalid')
            return data['result']
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError, UnicodeError):
            raise ProviderError('provider_unavailable')


def call(app, operation, method, params):
    if not app.state.settings.codeforces_enabled:
        raise ProviderError('provider_disabled')
    sessions = app.state.sessions
    token = acquire(sessions, operation, ttl_ms=45000)
    if token is None:
        raise ProviderError('provider_busy')
    global_token = None
    cooldown = 3000
    try:
        global_token = acquire(sessions, 'codeforces:global', spacing_ms=3000, ttl_ms=45000)
        if global_token is None:
            raise ProviderError('provider_busy')
        return app.state.codeforces.request(method, params)
    except ProviderError as exc:
        if exc.code in ('provider_rate_limited', 'provider_unavailable', 'provider_invalid'):
            cooldown = 60000
        raise
    finally:
        if global_token:
            release(sessions, 'codeforces:global', global_token, cooldown_ms=cooldown)
        release(sessions, operation, token)


def integer(value, nullable=True):
    if value is None and nullable:
        return None
    if type(value) is not int or not -10000 <= value <= 10**12:
        raise ProviderError('provider_invalid')
    return value


def profile(value):
    if not isinstance(value, dict) or not isinstance(value.get('handle'), str) or not HANDLE.fullmatch(value['handle']):
        raise ProviderError('provider_invalid')
    out = {'handle': value['handle'], 'rating': integer(value.get('rating')), 'max_rating': integer(value.get('maxRating')),
           'registration_time': integer(value.get('registrationTimeSeconds'))}
    for target, key in [('rank', 'rank'), ('max_rank', 'maxRank')]:
        v = value.get(key)
        if v is not None and (not isinstance(v, str) or len(v) > 80):
            raise ProviderError('provider_invalid')
        out[target] = v
    return out


def account_dto(account, cached):
    if account is None:
        return {'state': 'not_connected', 'account': None, 'server_now': now_ms()}
    state = account.approval_status
    if state == 'approved':
        state = 'approved_opted_in' if account.leaderboard_opt_in else 'approved_not_opted_in'
    return {'state': state, 'account': {
        'id': account.id, 'handle': account.handle, 'leaderboard_opt_in': account.leaderboard_opt_in,
        'approval_status': account.approval_status, 'approval_method': account.approval_method,
        'approved_at': account.approved_at, 'last_error': account.last_error,
        'last_success_at': account.last_success_at, 'next_refresh_at': account.next_refresh_at, 'version': account.version,
        'profile': profile_dto(cached) if cached else None,
    }, 'server_now': now_ms()}


def profile_dto(cached):
    return {'handle': cached.handle, 'rating': cached.rating, 'max_rating': cached.max_rating, 'rank': cached.rank,
            'last_updated_at': cached.fetched_at, 'profile_url': 'https://codeforces.com/profile/' + quote(cached.handle, safe='')}


def refresh_accounts(app, snapshots):
    """Snapshots are (id, version, normalized handle). No caller transaction is held.
    CAS-like revalidation prevents delayed responses from undoing disconnects,
    consent withdrawal, handle changes or staff decisions.
    """
    snapshots = snapshots[:20]
    if not snapshots:
        return
    handles = [s[2] for s in snapshots]
    data, error = None, None
    try:
        raw = call(app, 'codeforces:profiles', 'user.info', {'handles': ';'.join(handles), 'checkHistoricHandles': 'false'})
        if len(raw) != len(snapshots):
            raise ProviderError('provider_invalid')
        data = [profile(v) for v in raw]
    except ProviderError as exc:
        error = exc
    with app.state.sessions() as db:
        now = now_ms()
        for index, (account_id, version, normalized) in enumerate(snapshots):
            account = db.scalar(select(ExternalAccount).where(ExternalAccount.id == account_id).with_for_update())
            if account is None or account.version != version or account.normalized_handle != normalized:
                continue
            actor = db.get(User, account.user_id)
            subject = db.get(SubjectMembership, ('informatics', account.user_id))
            if not actor or not actor.active or actor.role != 'student' or not subject or not subject.active:
                continue
            account.last_attempt_at = now
            if error:
                # A batch's one invalid handle never invalidates everyone else.
                account.last_error = error.code if error.code != 'invalid_handle' or error.handle == normalized else 'provider_unavailable'
                account.next_refresh_at = now + (5000 if error.code == 'provider_busy' else 60000)
                if account.last_error == 'invalid_handle':
                    account.approval_status = 'invalid_handle'
                    account.approved_handle_key = None
                    account.version += 1
                continue
            value = data[index]
            if value['handle'].casefold() != normalized:
                # No historic alias transfer. The owner must submit the new name for review.
                account.approval_status, account.approved_handle_key = 'pending_validation', None
                account.last_error, account.next_refresh_at = 'handle_changed', now + 60000
                account.version += 1
                continue
            cached = db.get(CodeforcesProfile, account.id)
            changed_identity = cached is not None and cached.registration_time is not None and cached.registration_time != value['registration_time']
            if changed_identity:
                account.approval_status, account.approved_handle_key = 'pending_approval', None
                account.approved_at, account.approved_by, account.approval_method = None, None, None
                account.version += 1
            if cached is None:
                cached = CodeforcesProfile(account_id=account.id, **value, fetched_at=now)
                db.add(cached)
            else:
                for k, v in value.items():
                    setattr(cached, k, v)
                cached.fetched_at = now
            account.handle = value['handle']
            account.last_success_at, account.last_error = now, None
            account.next_refresh_at = now + app.state.settings.codeforces_profile_ttl_seconds * 1000
            if account.approval_status in ('pending_validation', 'invalid_handle'):
                account.approval_status = 'pending_approval'
                account.version += 1
        db.commit()


def upcoming(app):
    sessions = app.state.sessions
    with sessions() as db:
        insert_ignore(db, CodeforcesContestCache, {'id': 1, 'contests': [], 'next_refresh_at': 0}, ['id'])
        db.commit()
        cache = db.get(CodeforcesContestCache, 1)
        needs_refresh = cache.next_refresh_at <= now_ms()
        original_fetched_at = cache.fetched_at
    if needs_refresh:
        try:
            data = call(app, 'codeforces:contests', 'contest.list', {'gym': 'false'})
            contests = []
            now_s = now_ms() // 1000
            for entry in data:
                if not isinstance(entry, dict):
                    raise ProviderError('provider_invalid')
                if entry.get('phase') != 'BEFORE':
                    continue
                start = integer(entry.get('startTimeSeconds'))
                if start is None or start <= now_s:
                    continue
                cid, duration = integer(entry.get('id'), False), integer(entry.get('durationSeconds'), False)
                name = entry.get('name')
                if cid <= 0 or duration <= 0 or not isinstance(name, str) or not name.strip() or len(name) > 500:
                    raise ProviderError('provider_invalid')
                contests.append({'id': cid, 'name': name, 'starts_at': start * 1000, 'duration_seconds': duration, 'url': f'https://codeforces.com/contest/{cid}'})
            contests.sort(key=lambda c: (c['starts_at'], c['id']))
            with sessions() as db:
                cache = db.get(CodeforcesContestCache, 1)
                cache.contests, cache.fetched_at, cache.last_error = contests[:30], now_ms(), None
                cache.next_refresh_at = now_ms() + app.state.settings.codeforces_contest_ttl_seconds * 1000
                db.commit()
        except ProviderError as exc:
            with sessions() as db:
                cache = db.get(CodeforcesContestCache, 1)
                # A concurrent busy reader must not overwrite a completed refresh.
                if cache.fetched_at == original_fetched_at:
                    cache.last_error = exc.code
                    cache.next_refresh_at = now_ms() + (5000 if exc.code == 'provider_busy' else 60000)
                db.commit()
    with sessions() as db:
        cache = db.get(CodeforcesContestCache, 1)
        now = now_ms()
        return {'items': [c for c in cache.contests if c['starts_at'] > now][:5], 'last_updated_at': cache.fetched_at,
                'stale': bool(cache.last_error) or cache.fetched_at is None or cache.fetched_at + app.state.settings.codeforces_contest_ttl_seconds * 1000 <= now,
                'error': cache.last_error, 'available': cache.fetched_at is not None,
                'source_url': 'https://codeforces.com/contests', 'server_now': now}
