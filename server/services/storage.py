"""Private object adapters. No browser keys, signed URLs or arbitrary remote hosts.

REST contract: Supabase Storage Server Reference and API key guidance, reviewed
2026-10-14. Secret keys use apikey; legacy service_role JWTs also use Bearer.
The hosted authentication/policy contract still requires a staging smoke test.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Protocol, Iterator
from urllib.parse import quote
import httpx


class StorageError(Exception):
    pass


class StorageMissing(StorageError):
    pass


class StorageConflict(StorageError):
    pass


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    sha256: str


class ObjectReader(Protocol):
    def __iter__(self) -> Iterator[bytes]: ...
    def close(self) -> None: ...


class StorageBackend(Protocol):
    def put(self, key: str, data: bytes, media_type: str) -> None: ...
    def open_read(self, key: str) -> ObjectReader: ...
    def stat(self, key: str) -> ObjectInfo | None: ...
    def delete(self, key: str) -> None: ...


def key_valid(key: str) -> str:
    if not re.fullmatch(r'files/[0-9a-f-]{36}', key):
        raise StorageError('invalid_object_key')
    return key


def inspect_object(reader: ObjectReader, max_bytes=8*1024*1024) -> ObjectInfo:
    sha, size = hashlib.sha256(), 0
    try:
        for chunk in reader:
            size += len(chunk)
            if size > max_bytes:
                raise StorageError('object_too_large')
            sha.update(chunk)
        return ObjectInfo(size, sha.hexdigest())
    finally:
        reader.close()


class LocalReader:
    def __init__(self, path):
        try: self.file = path.open('rb')
        except FileNotFoundError: raise StorageMissing('object_missing')
    def __iter__(self):
        try:
            while chunk := self.file.read(65536): yield chunk
        finally: self.close()
    def close(self): self.file.close()


class LocalStorage:
    def __init__(self, directory: Path): self.directory = directory
    def path(self, key): return self.directory / key_valid(key).split('/')[1]
    def put(self, key, data, media_type):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = self.path(key)
        fd, name = tempfile.mkstemp(prefix='.pending-', dir=self.directory)
        try:
            with os.fdopen(fd, 'wb') as out:
                out.write(data); out.flush(); os.fsync(out.fileno())
            try: os.link(name, target)  # Atomic create-if-absent: never overwrite history.
            except FileExistsError: raise StorageConflict('object_exists')
        finally: Path(name).unlink(missing_ok=True)
    def open_read(self, key): return LocalReader(self.path(key))
    def stat(self, key):
        try: return inspect_object(self.open_read(key))
        except StorageMissing: return None
    def delete(self, key): self.path(key).unlink(missing_ok=True)


class HTTPReader:
    def __init__(self, client, response):
        self.client, self.response = client, response
        self.deadline = time.monotonic() + 30
        self.closed = False
    def __iter__(self):
        total = 0
        try:
            for chunk in self.response.iter_bytes():
                total += len(chunk)
                if total > 8*1024*1024 or time.monotonic() > self.deadline:
                    raise StorageError('bounded_read_exceeded')
                yield chunk
        except httpx.HTTPError:
            raise StorageError('storage_unavailable')
        finally: self.close()
    def close(self):
        if not self.closed:
            self.closed = True
            self.response.close(); self.client.close()


class SupabaseStorage:
    def __init__(self, url: str, bucket: str, key: str, transport=None):
        if not url.startswith('https://') or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,62}', bucket):
            raise ValueError('Invalid private Storage configuration')
        self.base = url.rstrip('/') + '/storage/v1'
        self.bucket, self.transport = bucket, transport
        self.headers = {'apikey': key, 'User-Agent': 'AdolatOlympicClub/2.0 backend'}
        if not key.startswith('sb_secret_'):
            # Legacy JWT support is explicit; do not put new opaque keys in Bearer.
            self.headers['Authorization'] = 'Bearer ' + key
    def client(self):
        return httpx.Client(timeout=httpx.Timeout(10, connect=5), headers=self.headers, transport=self.transport, follow_redirects=False)
    def url(self, key, authenticated=False):
        return self.base + '/object/' + ('authenticated/' if authenticated else '') + quote(self.bucket,safe='') + '/' + quote(key_valid(key),safe='/')
    @staticmethod
    def control_body(response):
        data = bytearray();deadline = time.monotonic() + 12
        for part in response.iter_bytes():
            data.extend(part)
            if len(data) > 16384 or time.monotonic() > deadline:
                raise StorageError('bounded_control_response_exceeded')
        try:
            value=json.loads(data)
            return value if isinstance(value,dict) else {}
        except (ValueError,UnicodeDecodeError):
            return {}

    @staticmethod
    def missing(status, body):
        return status == 404 or status == 400 and str(body.get('statusCode')) == '404'

    def put(self, key, data, media_type):
        try:
            with self.client() as client:
                with client.stream('POST',self.url(key),content=data,headers={'Content-Type':media_type,'x-upsert':'false','Cache-Control':'private, no-store'}) as response:
                    self.control_body(response)
                    if response.status_code in (400,409):raise StorageConflict('object_may_exist')
                    if not 200<=response.status_code<300:raise StorageError('storage_unavailable')
        except httpx.HTTPError:raise StorageError('storage_unavailable')

    def open_read(self, key):
        client=self.client();response=None
        try:
            response=client.send(client.build_request('GET',self.url(key,True)),stream=True)
            if response.status_code != 200:
                body=self.control_body(response)
                if self.missing(response.status_code,body):raise StorageMissing('object_missing')
                raise StorageError('storage_unavailable')
            return HTTPReader(client,response)
        except (httpx.HTTPError,StorageError) as exc:
            if response is not None:response.close()
            client.close()
            if isinstance(exc,StorageError):raise
            raise StorageError('storage_unavailable')

    def stat(self, key):
        # Byte-level verification, not trust in ETag or content-length semantics.
        try: return inspect_object(self.open_read(key))
        except StorageMissing: return None
    def delete(self, key):
        try:
            with self.client() as client:
                with client.stream('DELETE',self.url(key)) as response:
                    body=self.control_body(response)
                    if not 200<=response.status_code<300 and not self.missing(response.status_code,body):
                        raise StorageError('storage_unavailable')
        except httpx.HTTPError:raise StorageError('storage_unavailable')


def build_storage(settings):
    if settings.storage_backend=='supabase':
        return SupabaseStorage(settings.supabase_url, settings.supabase_storage_bucket, settings.supabase_storage_server_key)
    return LocalStorage(settings.data_dir/'uploads')
