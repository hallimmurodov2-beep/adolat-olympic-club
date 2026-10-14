# Offline recovery utility — synthetic / school-approved SQLite pilot ONLY

`python -m scripts.recovery` performs a **working**, password-encrypted SQLite snapshot plus all records' corresponding local private objects. It is **not** a Supabase PostgreSQL database backup, Supabase Storage export, typed school-data importer, production rollback, or permission to collect real student records.

## Preconditions

- A school-approved operator stops application writes and controls the source database and its *separate* private local file directory. Never back up a live production instance via an unapproved copy/paste step.
- Python 3.13+, the project's source, `gpg` on `PATH`, sufficient scratch and archive space, and a separately-held strong passphrase (minimum 16 characters).
- Source SQLite schema migrated to the correct checkpoint version and its local `stored_files` entries have stable `object_key`, SHA-256 and size. A non-local (`supabase`) object reference causes a hard error. A referenced missing/corrupt object also causes a hard error.
- Custodian stores encrypted archive and passphrase separately, and practices an isolated restore. The script will not overwrite an existing archive or an existing restoration directory.

## Commands

First, from the project root, **stop writes** and confirm the actual paths. In the current local adapter the directory containing private bytes normally resides under `DATA_DIR/uploads` (verify this on the machine and do not assume it in production).

```bash
python -m scripts.recovery backup \
  --db /safe/offline-copy/olympiados.db \
  --uploads /safe/offline-copy/uploads \
  --output /secure/offsite/adolat-pilot-20261014.tar.gpg \
  --maintenance-confirmed

python -m scripts.recovery verify \
  --archive /secure/offsite/adolat-pilot-20261014.tar.gpg

python -m scripts.recovery restore \
  --archive /secure/offsite/adolat-pilot-20261014.tar.gpg \
  --target /isolated/restore-check-20261014
```

Each command prompts for the passphrase, never passes it in the process argument list, and returns a failure status on wrong passphrase, missing file, corrupt integrity, invalid archive structure, or overwrite attempt. The restored files are `olympiados.db` and `uploads/<uuid>` under the new target. Verification checks SQLite integrity and **every referenced private object's SHA-256 and byte count**, rather than just whether the archive decrypts. Test coverage: `tests/test_v2_recovery.py` with real GnuPG.

## Operational boundary

Backup creation requires a maintenance confirmation and a coordinated write-stop because the SQLite online backup and object copy are not an atomic transaction across the filesystem. Files not referenced from `stored_files` are not archived and need separate retention/reconciliation decisions. The utility has explicit per-object and DB limits; it will fail closed rather than silently back up oversize/unrecognized references. Backups can contain private student content: do not email them or include them in source ZIPs.

**Required before real Supabase cutover:** build and execute a separately authorized PostgreSQL consistent snapshot/restore mechanism (with compatible `pg_dump`/`pg_restore`, privileges and extension policy), an authenticated private Storage export/restore/manifest verifier, full V1-to-V2 typed data/relationship reconciliation, backups after V2 writes, and a reversible live staging restore drill witnessed by the school-designated custodian. This utility does not meet that gate.
