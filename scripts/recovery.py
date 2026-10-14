"""Offline encrypted snapshot/restore for a SQLite + private-local-storage PILOT.

Not a PostgreSQL-to-Supabase cutover importer. Never run over an active school's
production database. Back up files with their DB; verify before restoring.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from getpass import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
from typing import Iterator
from uuid import UUID

MAX_OBJECT = 8 * 1024 * 1024
MAX_DB = 2 * 1024 * 1024 * 1024
MAX_FILES = 100000


def checksum_file(path: Path) -> str:
    hash = hashlib.sha256()
    with path.open('rb') as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b''):
            hash.update(chunk)
    return hash.hexdigest()


def snapshot_db(source: Path, destination: Path):
    # sqlite3.backup is a transactionally consistent copy even with WAL enabled.
    src = sqlite3.connect(f'file:{source}?mode=ro', uri=True)
    try:
        if src.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('source_integrity_failed')
        dst = sqlite3.connect(destination)
        try: src.backup(dst)
        finally: dst.close()
    finally: src.close()
    destination.chmod(0o600)


def references(db_path: Path) -> list[dict]:
    with sqlite3.connect(db_path) as connection:
        records = connection.execute('SELECT id,storage_backend,object_key,sha256,size FROM stored_files ORDER BY id').fetchall()
    if len(records) > MAX_FILES:
        raise ValueError('too_many_objects')
    output = []
    for fid, backend, key, sha, size in records:
        if backend != 'local' or key != 'files/' + fid or not re.fullmatch(r'[0-9a-f-]{36}', fid) or str(UUID(fid)) != fid:
            raise ValueError('unsupported_storage_reference:' + fid)
        if not isinstance(size, int) or not 0 < size <= MAX_OBJECT or not re.fullmatch('[0-9a-f]{64}', sha or ''):
            raise ValueError('missing_storage_checksum:' + fid)
        output.append({'id': fid, 'size': size, 'sha256': sha})
    return output


def stored_files_match(db: Path, objects: Path, expected: list[dict]):
    if references(db) != expected:
        raise ValueError('database_manifest_mismatch')
    for record in expected:
        path = objects / record['id']
        if not path.is_file() or path.is_symlink() or path.stat().st_size != record['size'] or checksum_file(path) != record['sha256']:
            raise ValueError('object_checksum_mismatch:' + record['id'])


@contextmanager
def gpg_stream(args: list[str], password: str) -> Iterator[subprocess.Popen]:
    if not password or len(password) < 16:
        raise ValueError('A separate strong backup passphrase (16+ characters) is required')
    fd, out = os.pipe()
    try:
        proc = subprocess.Popen(['gpg', '--batch', '--no-tty', '--pinentry-mode', 'loopback',
             '--passphrase-fd', str(fd), *args], pass_fds=(fd,), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    finally: os.close(fd)
    try:
        os.write(out, password.encode('utf-8') + b'\n')
    finally: os.close(out)
    try:
        yield proc
        if proc.stdin and not proc.stdin.closed: proc.stdin.close()
        if proc.wait(timeout=120) != 0:
            raise ValueError('encrypted_archive_failure')
    except BaseException:
        proc.kill() if proc.poll() is None else None
        proc.wait()
        raise
    finally:
        proc.stdin and proc.stdin.close()
        proc.stdout and proc.stdout.close()


def _tarfile(tar: tarfile.TarFile, filename: str, path: Path):
    record = tarfile.TarInfo(filename)
    record.size = path.stat().st_size
    record.mode = 0o600
    with path.open('rb') as inp:
        tar.addfile(record, inp)


def backup(source_db: Path, upload_directory: Path, destination: Path, password: str) -> dict:
    if destination.exists():
        raise FileExistsError('Refusing to overwrite existing backup')
    if not source_db.is_file() or source_db.is_symlink():
        raise ValueError('SQLite source file is missing or unsafe')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='aoc-snapshot-') as workspace:
        root = Path(workspace)
        os.chmod(root, 0o700)
        db = root / 'snapshot.sqlite'
        snapshot_db(source_db, db)
        entries = references(db)
        for entry in entries:
            obj = upload_directory / entry['id']
            if not obj.is_file() or obj.is_symlink() or obj.stat().st_size != entry['size'] or checksum_file(obj) != entry['sha256']:
                raise ValueError('source_object_missing_or_changed:' + entry['id'])
        manifest = {'format': 'adolat-pilot-recovery-v1', 'database_sha256': checksum_file(db),
                    'objects': entries, 'object_count': len(entries)}
        manifest_path = root / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
        manifest_path.chmod(0o600)
        target = root / 'encrypted.tmp'
        with gpg_stream(['--symmetric', '--cipher-algo', 'AES256', '--s2k-mode', '3',
                         '--s2k-digest-algo', 'SHA512', '--s2k-count', '65011712',
                         '--compress-algo', 'none', '--output', str(target)], password) as proc:
            assert proc.stdin
            with tarfile.open(fileobj=proc.stdin, mode='w|') as tar:
                _tarfile(tar, 'manifest.json', manifest_path)
                _tarfile(tar, 'database.sqlite', db)
                for entry in entries:
                    _tarfile(tar, 'objects/' + entry['id'], upload_directory / entry['id'])
        target.chmod(0o600)
        os.replace(target, destination)
        return {'archive': str(destination), 'object_count': len(entries), 'database_sha256': manifest['database_sha256']}


def unpack_checked(archive: Path, root: Path, password: str) -> dict:
    if not archive.is_file() or archive.is_symlink():
        raise ValueError('encrypted_backup_missing')
    with gpg_stream(['--decrypt', str(archive)], password) as proc:
        assert proc.stdout
        manifest = None
        seen: set[str] = set()
        total = 0
        with tarfile.open(fileobj=proc.stdout, mode='r|') as tar:
            for entry in tar:
                name = entry.name
                if not entry.isfile() or name in seen or (name not in ('manifest.json', 'database.sqlite')
                      and not re.fullmatch(r'objects/[0-9a-f-]{36}', name)):
                    raise ValueError('unsafe_backup_member')
                seen.add(name)
                if entry.size > (MAX_DB if name == 'database.sqlite' else (4 * 1024 * 1024 if name == 'manifest.json' else MAX_OBJECT)):
                    raise ValueError('oversized_backup_member')
                total += entry.size
                if total > MAX_DB + MAX_FILES * MAX_OBJECT:
                    raise ValueError('oversized_backup')
                inp = tar.extractfile(entry)
                if inp is None: raise ValueError('bad_backup_member')
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open('xb') as output:
                    shutil.copyfileobj(inp, output, 1024 * 1024)
                dest.chmod(0o600)
        if seen != {'manifest.json', 'database.sqlite'} | {k for k in seen if k.startswith('objects/')}:
            raise ValueError('backup_missing_database')
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('format') != 'adolat-pilot-recovery-v1': raise ValueError('unsupported_snapshot_format')
        objects = manifest.get('objects')
        if not isinstance(objects, list) or len(objects) > MAX_FILES or len(objects) != manifest.get('object_count'):
            raise ValueError('invalid_manifest')
        expected = {'manifest.json', 'database.sqlite'} | {'objects/' + x['id'] for x in objects}
        if seen != expected or checksum_file(root / 'database.sqlite') != manifest.get('database_sha256'):
            raise ValueError('backup_checksum_mismatch')
        db = root / 'database.sqlite'
        with sqlite3.connect(f'file:{db}?mode=ro', uri=True) as conn:
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('backup_integrity_failed')
        stored_files_match(db, root / 'objects', objects)
        return manifest


def verify(archive: Path, password: str) -> dict:
    with tempfile.TemporaryDirectory(prefix='aoc-verify-') as tmp:
        root = Path(tmp); os.chmod(root, 0o700)
        try: return unpack_checked(archive, root, password)
        except tarfile.TarError as exc: raise ValueError('Decryption failed or archive invalid') from exc


def restore(archive: Path, target: Path, password: str) -> dict:
    # Restore is always a new isolated directory. Never overwrite an existing DB.
    if target.exists(): raise FileExistsError('Target already exists; use a new isolated recovery directory')
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.aoc-restore-', dir=target.parent) as tmp:
        root = Path(tmp); os.chmod(root, 0o700)
        try: manifest = unpack_checked(archive, root, password)
        except tarfile.TarError as exc: raise ValueError('Decryption failed or archive invalid') from exc
        output = root / 'restored'
        output.mkdir(mode=0o700)
        (output / 'uploads').mkdir(mode=0o700)
        os.replace(root / 'database.sqlite', output / 'olympiados.db')
        for obj in manifest['objects']:
            os.replace(root / 'objects' / obj['id'], output / 'uploads' / obj['id'])
        os.replace(output, target)
        return {'target': str(target), 'object_count': manifest['object_count']}


def main():
    parser = argparse.ArgumentParser(description='OFFLINE encrypted SQLite/private-local pilot backup and isolated restore')
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('backup')
    b.add_argument('--db', type=Path, required=True)
    b.add_argument('--uploads', type=Path, required=True)
    b.add_argument('--output', type=Path, required=True)
    b.add_argument('--maintenance-confirmed', action='store_true')
    v = sub.add_parser('verify'); v.add_argument('--archive', type=Path, required=True)
    r = sub.add_parser('restore'); r.add_argument('--archive', type=Path, required=True); r.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'backup' and not args.maintenance_confirmed:
        parser.error('Stop application writes first, then explicitly pass --maintenance-confirmed')
    password = getpass('Offline backup passphrase: ')
    if args.command == 'backup': result = backup(args.db, args.uploads, args.output, password)
    elif args.command == 'verify': result = verify(args.archive, password)
    else: result = restore(args.archive, args.target, password)
    print(json.dumps({k:v for k,v in result.items() if k != 'objects'}, indent=2))


if __name__ == '__main__': main()
