"""Short durable reservations. Never sleep or perform network I/O in a transaction."""
from sqlalchemy import update
from ..models import OperationLease, now_ms, uid


def insert_ignore(db, model, values, keys):
    from sqlalchemy.dialects.sqlite import insert as sq_insert
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    insert = sq_insert if db.bind.dialect.name == 'sqlite' else pg_insert
    db.execute(insert(model).values(**values).on_conflict_do_nothing(index_elements=keys))


def acquire(sessions, name, spacing_ms=0, ttl_ms=20000):
    token, now = uid(), now_ms()
    with sessions() as db:
        insert_ignore(db, OperationLease, {'name': name, 'not_before': 0, 'expires_at': 0, 'owner': '', 'state': {}}, ['name'])
        result = db.execute(update(OperationLease).where(OperationLease.name == name, OperationLease.not_before <= now, OperationLease.expires_at <= now).values(not_before=now + spacing_ms, expires_at=now + ttl_ms, owner=token))
        db.commit()
        return token if result.rowcount == 1 else None


def release(sessions, name, token, cooldown_ms=None):
    with sessions() as db:
        values = {'expires_at': 0, 'owner': ''}
        if cooldown_ms is not None:
            values['not_before'] = now_ms() + cooldown_ms
        db.execute(update(OperationLease).where(OperationLease.name == name, OperationLease.owner == token).values(**values))
        db.commit()
