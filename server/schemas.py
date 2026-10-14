"""Every mutation has a closed schema: client-supplied role/score/owner fields are rejected."""
from __future__ import annotations
from typing import Annotated, Literal
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BiText = Annotated[dict[Literal['ru', 'en'], str], Field(max_length=2)]
Locale = Literal['ru', 'en']
Language = Literal['written', 'python', 'cpp']
Identifier = Annotated[str, Field(pattern=r'^[a-zA-Z0-9-]{1,36}$')]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False, allow_inf_nan=False)

    @field_validator('*', mode='before')
    @classmethod
    def bound_content(cls, value):
        if isinstance(value, dict) and set(value).issubset({'ru', 'en'}):
            if any(not isinstance(v, str) or len(v) > 50000 for v in value.values()):
                raise ValueError('content_limit')
            return {k: v.strip() for k, v in value.items() if v.strip()}
        return value


class LoginInput(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    locale: Locale | None = None


class InvitationTokenInput(Input):
    token: str = Field(min_length=30, max_length=128)


class RegisterInput(Input):
    token: str = Field(min_length=30, max_length=128)
    display_name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=12, max_length=256)
    locale: Locale = 'ru'


class PasswordInput(Input):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class ProfileInput(Input):
    display_name: str | None = Field(default=None, min_length=2, max_length=100)
    locale: Locale | None = None


class InviteInput(Input):
    email: str = Field(min_length=3, max_length=254)
    role: Literal['teacher', 'student']
    classroom_id: Identifier | None = None

    @field_validator('email')
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
            raise ValueError('invalid_email')
        return value


class ActiveInput(Input):
    active: bool


class ClubInput(Input):
    name: BiText = Field(min_length=1)
    timezone: str = Field(max_length=60)

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('invalid_timezone')
        return value


class TopicInput(Input):
    subject_id: Identifier
    name: BiText = Field(min_length=1)


class ClassroomInput(Input):
    subject_id: Identifier
    teacher_id: Identifier | None = None
    name: BiText = Field(min_length=1)
    description: BiText = Field(default_factory=dict)


class ClassroomEdit(Input):
    name: BiText = Field(min_length=1)
    description: BiText = Field(default_factory=dict)
    active: bool = True


class MemberInput(Input):
    user_id: Identifier


class AnnouncementInput(Input):
    body: BiText = Field(min_length=1)


class ResourceInput(Input):
    title: BiText = Field(min_length=1)
    body: BiText = Field(default_factory=dict)
    topic_id: Identifier | None = None
    url: str | None = Field(default=None, max_length=2000)

    @field_validator('url')
    @classmethod
    def safe_url(cls, value):
        if value and (not value.startswith('https://') or re.search(r'[\s\\\x00-\x1f]', value)):
            raise ValueError('https_only')
        return value or None


class ProblemInput(Input):
    classroom_id: Identifier
    topic_id: Identifier | None = None
    title: BiText = Field(min_length=1)
    statement: BiText = Field(min_length=1)
    subtopic: BiText = Field(default_factory=dict)
    hints: BiText = Field(default_factory=dict)
    solution: BiText = Field(default_factory=dict)
    examples: BiText = Field(default_factory=dict)
    difficulty: int = Field(default=2, ge=1, le=5)
    source: str = Field(default='', max_length=300)
    year: int | None = Field(default=None, ge=1900, le=2200)
    tags: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list, max_length=15)
    format: Literal['written', 'code'] = 'written'
    published: bool = False
    version: int | None = Field(default=None, ge=1)


class SetInput(Input):
    classroom_id: Identifier
    title: BiText = Field(min_length=1)
    description: BiText = Field(default_factory=dict)
    problem_ids: list[Identifier] = Field(min_length=1, max_length=40)


class Criterion(Input):
    name: BiText = Field(min_length=1)
    max: float = Field(gt=0, le=1000)


class ItemInput(Input):
    problem_id: Identifier
    points: float = Field(gt=0, le=1000, default=7)
    rubric: list[Criterion] = Field(default_factory=list, max_length=20)

    @model_validator(mode='after')
    def rubric_total(self):
        if self.rubric and not math.isclose(sum(c.max for c in self.rubric), self.points, abs_tol=0.001):
            raise ValueError('rubric_total')
        return self


class ActivityInput(Input):
    classroom_id: Identifier
    kind: Literal['assignment', 'session', 'competition']
    title: BiText = Field(min_length=1)
    description: BiText = Field(default_factory=dict)
    starts_at: int | None = Field(default=None, ge=0)
    ends_at: int | None = Field(default=None, ge=0)
    duration_minutes: int = Field(default=60, ge=1, le=600)
    items: list[ItemInput] = Field(min_length=1, max_length=40)
    eligible_ids: list[Identifier] | None = Field(default=None, max_length=500)

    @model_validator(mode='after')
    def times(self):
        if self.kind == 'competition' and (self.starts_at is None or self.ends_at is None):
            raise ValueError('competition_times')
        if self.starts_at is not None and self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError('time_order')
        if len({i.problem_id for i in self.items}) != len(self.items):
            raise ValueError('duplicate_problems')
        return self


class ActivityDraftEdit(Input):
    """Draft-only metadata; item snapshots, participant rosters and grades are immutable."""
    edit_version: int = Field(ge=1)
    title: BiText = Field(min_length=1)
    description: BiText = Field(default_factory=dict)
    starts_at: int | None = Field(default=None, ge=0)
    ends_at: int | None = Field(default=None, ge=0)
    duration_minutes: int = Field(default=60, ge=1, le=600)

    @model_validator(mode='after')
    def valid_window(self):
        if self.starts_at is not None and self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError('time_order')
        return self


class InterruptionExtension(Input):
    """Audited exceptional extension; never rewrites prior submission timestamps."""
    expected_ends_at: int = Field(ge=1)
    new_ends_at: int = Field(ge=1)
    reason: str = Field(min_length=20, max_length=500)


class ControlInput(Input):
    action: Literal['publish', 'start', 'end', 'publish_results', 'announce']
    body: BiText = Field(default_factory=dict)


class ReleaseInput(Input):
    action: Literal['problem', 'hints', 'solution']
    enabled: bool = True


class HelpInput(Input):
    body: str = Field(min_length=1, max_length=1000)


class WorkInput(Input):
    content: str = Field(default='', max_length=50000)
    language: Language = 'written'
    revision: int = Field(ge=0)


class SubmissionInput(Input):
    activity_item_id: Identifier
    content: str = Field(default='', max_length=50000)
    language: Language = 'written'
    group_id: Identifier | None = None
    group_revision: int | None = Field(default=None, ge=0)
    file_ids: list[Identifier] = Field(default_factory=list, max_length=12)
    client_id: str = Field(pattern=r'^[0-9a-fA-F-]{36}$')


class GradeInput(Input):
    score: float | None = Field(default=None, ge=0, le=1000)
    criterion_scores: list[Annotated[float, Field(ge=0, le=1000)]] = Field(default_factory=list, max_length=20)
    feedback: BiText = Field(default_factory=dict)
    status: Literal['reviewed', 'revision_requested'] = 'reviewed'
    release: bool = False
    version: int = Field(ge=0)


class GroupInput(Input):
    classroom_id: Identifier
    activity_item_id: Identifier
    name: str = Field(min_length=1, max_length=100)
    user_ids: list[Identifier] = Field(min_length=1, max_length=12)
    shared: bool = False


class ShareInput(Input):
    shared: bool


class CommentInput(Input):
    body: str = Field(min_length=1, max_length=5000)
