from __future__ import annotations
from typing import Any

class DomainError(Exception):
    def __init__(self, code: str, status: int = 400, data: dict[str, Any] | None = None):
        self.code, self.status, self.data = code, status, data or {}
        super().__init__(code)


def require(condition: object, code: str = 'forbidden', status: int = 403) -> None:
    if not condition:
        raise DomainError(code, status)
