from __future__ import annotations
import ipaddress
import re
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from .schemas import Input, BiText, Identifier

Outcome = Literal['not_started', 'attempted', 'revisit', 'completed']
Assistance = Literal['independent', 'hints', 'editorial', 'peer']


def safe_external_url(value: str) -> str:
    value = value.strip()
    if len(value) > 2000 or any(ord(c) <= 32 for c in value) or '\\' in value:
        raise ValueError('invalid_url')
    try:
        p = urlsplit(value)
        host = (p.hostname or '').encode('idna').decode().lower()
        if p.scheme != 'https' or not host or p.username or p.password or p.port not in (None, 443):
            raise ValueError('invalid_url')
        if '.' not in host or host.endswith(('.local', '.localhost', '.internal')):
            raise ValueError('invalid_url')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError('invalid_url')
        return urlunsplit(('https', host, p.path or '/', p.query, p.fragment))
    except (UnicodeError, ValueError):
        raise ValueError('invalid_url')


class TrainingInput(Input):
    @field_validator('*', mode='before')
    @classmethod
    def small_text(cls, value):
        if isinstance(value, dict) and set(value).issubset({'en', 'ru'}):
            if any(not isinstance(v, str) or len(v) > 2000 for v in value.values()):
                raise ValueError('text_limit')
        return value


class LinkInput(TrainingInput):
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=2000)
    _url = field_validator('url')(safe_external_url)
    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError('empty_title')
        return value.strip()


class CycleInput(TrainingInput):
    client_id: UUID
    circle_id: Identifier | None = None
    title: BiText = Field(min_length=1)
    guidance: BiText = Field(default_factory=dict)
    links: list[LinkInput] = Field(default_factory=list, max_length=20)
    starts_at: int = Field(ge=0)
    ends_at: int = Field(ge=0)
    practice_starts_at: int | None = Field(default=None, ge=0)
    practice_ends_at: int | None = Field(default=None, ge=0)
    discussion_opens_at: int | None = Field(default=None, ge=0)
    mode: Literal['individual', 'collaborative'] = 'individual'
    status: Literal['draft', 'published'] = 'published'
    @model_validator(mode='after')
    def validate_times(self):
        if self.ends_at <= self.starts_at or self.ends_at - self.starts_at > 366 * 86400000:
            raise ValueError('invalid_times')
        if self.circle_id:
            if None in (self.practice_starts_at, self.practice_ends_at, self.discussion_opens_at):
                raise ValueError('practice_times_required')
            if not self.starts_at <= self.practice_starts_at < self.practice_ends_at <= self.ends_at:
                raise ValueError('practice_times_invalid')
            if not self.starts_at <= self.discussion_opens_at <= self.ends_at:
                raise ValueError('discussion_times_invalid')
            if self.mode == 'individual' and self.discussion_opens_at < self.practice_ends_at:
                raise ValueError('discussion_before_practice_end')
        elif self.links or self.mode != 'individual':
            raise ValueError('private_cycle_links_belong_in_plan')
        return self


class CycleEdit(CycleInput):
    version: int = Field(ge=1)
    status: Literal['draft', 'published', 'cancelled'] = 'published'


class PlanInput(TrainingInput):
    version: int = Field(ge=0)
    goal: BiText = Field(default_factory=dict)
    review: BiText = Field(default_factory=dict)
    next_step: BiText = Field(default_factory=dict)


class ItemInput(LinkInput):
    client_id: UUID
    carried_from_id: Identifier | None = None


class ItemEdit(LinkInput):
    version: int = Field(ge=1)
    status: Outcome


class EntryInput(TrainingInput):
    client_id: UUID
    item_version: int = Field(ge=1)
    outcome: Outcome
    assistance: Assistance = 'independent'
    reflection: BiText = Field(default_factory=dict)
    next_step: BiText = Field(default_factory=dict)


class CircleInput(TrainingInput):
    client_id: UUID
    name: BiText = Field(min_length=1)
    description: BiText = Field(default_factory=dict)
    discoverable: bool = True


class CircleEdit(TrainingInput):
    version: int = Field(ge=1)
    name: BiText = Field(min_length=1)
    description: BiText = Field(default_factory=dict)
    discoverable: bool = True
    archived: bool = False


class MemberAction(Input):
    action: Literal['approve', 'remove', 'transfer', 'consent_transfer', 'decline_transfer']
    user_id: Identifier


class PostInput(TrainingInput):
    client_id: UUID
    kind: Literal['help', 'explanation', 'logistics'] = 'explanation'
    body: BiText = Field(min_length=1)


class ReportInput(Input):
    circle_id: Identifier
    post_id: Identifier | None = None
    reason: Literal['unsafe', 'spoiler', 'harassment', 'facilitator', 'other']
    detail: str = Field(default='', max_length=1000)


class ReasonInput(Input):
    reason: str = Field(min_length=3, max_length=1000)
    @field_validator('reason')
    @classmethod
    def nonempty(cls, value):
        if len(value.strip()) < 3:
            raise ValueError('reason_required')
        return value.strip()


class ReportResolve(ReasonInput):
    hide_post: bool = False
    lock_circle: bool = False


class CircleLock(ReasonInput):
    locked: bool


class SubjectInput(Input):
    active: bool


class AccountInput(Input):
    handle: str = Field(min_length=3, max_length=24)
    consent: Literal[True]
    @field_validator('handle')
    @classmethod
    def handle_valid(cls, value):
        value = value.strip()
        if not re.fullmatch(r'[A-Za-z0-9_.-]{3,24}', value):
            raise ValueError('invalid_handle')
        return value


class RankingConsent(Input):
    opt_in: bool


class ApprovalInput(Input):
    version: int = Field(ge=1)
    action: Literal['approve', 'reject', 'revoke']
    method: Literal['observed_login', 'school_equivalent'] | None = None
    reason: str = Field(default='', max_length=500)
    @model_validator(mode='after')
    def evidence(self):
        if self.action == 'approve' and not self.method:
            raise ValueError('method_required')
        if self.action != 'approve' and len(self.reason.strip()) < 3:
            raise ValueError('reason_required')
        return self
