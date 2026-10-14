"""Small-host admission. One image/Argon2 operation; two upload buffers per process.

No security parameter is weakened. Busy requests get a translated, retryable 503
rather than creating an unbounded queue. The deployment contract is one worker.
"""
from contextlib import contextmanager
from threading import BoundedSemaphore
from ..errors import DomainError

CPU = BoundedSemaphore(1)
UPLOADS = BoundedSemaphore(2)


@contextmanager
def admit(pool=CPU):
    if not pool.acquire(blocking=False):
        raise DomainError('busy', 503)
    try:
        yield
    finally:
        pool.release()
