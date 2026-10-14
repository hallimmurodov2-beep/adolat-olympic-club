"""Stable, opaque timestamp/ID cursors. No user-supplied SQL."""
import base64
import json
from sqlalchemy import and_, or_
from ..errors import DomainError

def page_cursor(row):
    return base64.urlsafe_b64encode(json.dumps([row.created_at, row.id], separators=(',', ':')).encode()).decode().rstrip('=')

def apply_before(query, model, cursor):
    if not cursor:
        return query
    try:
        if len(cursor) > 180:
            raise ValueError()
        at, key = json.loads(base64.urlsafe_b64decode(cursor + '=' * (-len(cursor) % 4)))
        if type(at) is not int or not isinstance(key, str) or len(key) > 36:
            raise ValueError()
    except Exception:
        raise DomainError('invalid_input', 422)
    return query.where(or_(model.created_at < at, and_(model.created_at == at, model.id < key)))
