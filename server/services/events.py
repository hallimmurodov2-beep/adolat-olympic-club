from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import AuditLog, Event, Membership, Notification


def emit(db: Session, kind: str, entity_id: str, classroom_id: str | None = None, user_id: str | None = None, group_id: str | None = None) -> None:
    db.add(Event(kind=kind, entity_id=entity_id, classroom_id=classroom_id, user_id=user_id, group_id=group_id))


def audit(db: Session, actor_id: str, action: str, entity_id: str, detail: dict | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, entity_id=entity_id, detail=detail or {}))


def notify(db: Session, user_ids: list[str], kind: str, title: dict, link: str) -> None:
    for user_id in set(user_ids):
        item = Notification(user_id=user_id, kind=kind, title=title, link=link)
        db.add(item)
        db.flush()
        emit(db, 'notification', item.id, user_id=user_id)


def class_students(db: Session, classroom_id: str) -> list[str]:
    return list(db.scalars(select(Membership.user_id).where(Membership.classroom_id == classroom_id)))
