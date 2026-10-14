"""Real GPG-backed pilot backup/restore; no plaintext archive or overwrite."""
from __future__ import annotations
import hashlib
import shutil
import sqlite3
from uuid import uuid4
import pytest
from scripts.recovery import backup, restore, verify

pytestmark=pytest.mark.skipif(shutil.which('gpg') is None,reason='GnuPG is required for the encrypted recovery CLI')
PASSPHRASE='test-only-backup-passphrase-long-2026'


def test_encrypted_snapshot_includes_database_and_objects(env,tmp_path):
    db=tmp_path/'source.db';shutil.copy2(env.app.state.settings.data_dir/'test.db',db)
    folder=tmp_path/'uploads';folder.mkdir()
    identifier=str(uuid4());data=b'Example strictly private document bytes.\n';(folder/identifier).write_bytes(data)
    sha=hashlib.sha256(data).hexdigest()
    with sqlite3.connect(db) as conn:
        conn.execute('INSERT INTO stored_files(id,owner_id,classroom_id,target_kind,target_id,filename,media_type,size,created_at,storage_backend,object_key,sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
             (identifier,env.users['teacher'],env.rooms['math'],'problem',env.problems[0],'test.txt','text/plain',len(data),1000,'local','files/'+identifier,sha))
    archive=tmp_path/'pilot.gpg'
    result=backup(db,folder,archive,PASSPHRASE)
    assert result['object_count']==1
    assert archive.read_bytes()[:6]!=b'SQLite'
    assert data not in archive.read_bytes()
    metadata=verify(archive,PASSPHRASE)
    assert metadata['objects'][0]['sha256']==sha
    restored=tmp_path/'isolated'
    out=restore(archive,restored,PASSPHRASE)
    assert out['object_count']==1 and (restored/'uploads'/identifier).read_bytes()==data
    with sqlite3.connect(restored/'olympiados.db') as conn:
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]>=1
    with pytest.raises(FileExistsError):restore(archive,restored,PASSPHRASE)
    with pytest.raises((ValueError,OSError)):verify(archive,'incorrect-passphrase-123')


def test_backup_refuses_missing_object_before_writing_archive(env,tmp_path):
    db=tmp_path/'snapshot-input.db';shutil.copy2(env.app.state.settings.data_dir/'test.db',db)
    identifier=str(uuid4());data=b'missing';sha=hashlib.sha256(data).hexdigest()
    with sqlite3.connect(db) as conn:
        conn.execute('INSERT INTO stored_files(id,owner_id,classroom_id,target_kind,target_id,filename,media_type,size,created_at,storage_backend,object_key,sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
             (identifier,env.users['teacher'],env.rooms['math'],'problem',env.problems[0],'test.txt','text/plain',len(data),1000,'local','files/'+identifier,sha))
    archive=tmp_path/'missing.gpg'
    with pytest.raises(ValueError,match='source_object_missing_or_changed'):
        backup(db,tmp_path,archive,PASSPHRASE)
    assert not archive.exists()
