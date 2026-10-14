"""Per-process cache of *unfiltered metadata*, never of user-authorized content.

The only shared values are event scope/identifiers. Each delivery checks the current
session and resource permissions in its own short transaction. Slow SQL runs off
ASGI's event loop. A cold cursor uses a bounded database page.
"""
from __future__ import annotations
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from sqlalchemy import func, select
from ..models import Event


@dataclass(frozen=True)
class Candidate:
    id: int
    kind: str
    entity_id: str
    classroom_id: str | None
    user_id: str | None
    group_id: str | None


class EventFeed:
    def __init__(self):
        self.lock = Lock()
        self.refreshed = 0.0
        self.items: list[Candidate] = []
        self.minimum = 0
        self.maximum = 0

    @staticmethod
    def candidates(rows):
        return [Candidate(r.id, r.kind, r.entity_id, r.classroom_id, r.user_id, r.group_id) for r in rows]

    def read(self, db, cursor):
        with self.lock:
            if monotonic() - self.refreshed >= .75:
                bounds = db.execute(select(func.min(Event.id), func.max(Event.id))).one()
                self.minimum, self.maximum = bounds[0] or 0, bounds[1] or 0
                self.items = self.candidates(reversed(list(db.scalars(select(Event).order_by(Event.id.desc()).limit(400)))))
                self.refreshed = monotonic()
            # Retention gaps and restored databases require an authorized full refetch.
            reset = bool(cursor > self.maximum or cursor > 0 and self.minimum and cursor < self.minimum - 1)
            if reset:
                return [], self.maximum, True
            if self.items and cursor >= self.items[0].id - 1:
                return [r for r in self.items if r.id > cursor][:200], self.maximum, False
        rows = db.scalars(select(Event).where(Event.id > cursor).order_by(Event.id).limit(200))
        return self.candidates(rows), self.maximum, False
