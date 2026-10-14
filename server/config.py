"""Configuration. Production deliberately fails closed on missing secrets/origin."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    secret: str
    production: bool
    origin: str
    max_upload_bytes: int = 8 * 1024 * 1024
    user_quota_bytes: int = 200 * 1024 * 1024
    teacher_quota_bytes: int = 128 * 1024 * 1024
    session_seconds: int = 60 * 60 * 24 * 7

    db_schema: str = 'olympiados'
    pool_size: int = 2
    max_overflow: int = 1
    storage_backend: str = 'local'
    supabase_url: str = ''
    supabase_storage_bucket: str = 'olympiados-attachments'
    supabase_storage_server_key: str = ''
    storage_hard_limit_bytes: int = 700 * 1024 * 1024
    storage_soft_limit_bytes: int = 500 * 1024 * 1024
    circles_enabled: bool = True
    codeforces_enabled: bool = True
    codeforces_sync_enabled: bool = False
    codeforces_profile_ttl_seconds: int = 21600
    codeforces_contest_ttl_seconds: int = 1200

    def __post_init__(self):
        import re
        from urllib.parse import urlsplit, parse_qs
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,40}', self.db_schema) or self.db_schema in ('public','auth','storage'):
            raise ValueError('DB_SCHEMA must be a dedicated private schema.')
        if self.storage_backend not in ('local', 'supabase'):
            raise ValueError('Unsupported STORAGE_BACKEND.')
        if self.production:
            if not self.database_url.startswith(('postgresql://', 'postgresql+psycopg://')):
                raise ValueError('Production requires explicit PostgreSQL persistence, never SQLite.')
            query = parse_qs(urlsplit(self.database_url).query)
            if query.get('sslmode') != ['verify-full']:
                raise ValueError('Production database requires sslmode=verify-full and a trusted CA.')
            if self.storage_backend != 'supabase':
                raise ValueError('Production requires durable private Supabase Storage.')
        if self.storage_backend == 'supabase':
            p = urlsplit(self.supabase_url)
            if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('', '/'):
                raise ValueError('SUPABASE_URL must be the HTTPS project origin.')
            if not self.supabase_storage_server_key:
                raise ValueError('Private Storage requires a server-only key.')
        if not (0 < self.max_upload_bytes <= 8 * 1024 * 1024 and 0 < self.storage_soft_limit_bytes <= self.storage_hard_limit_bytes):
            raise ValueError('Invalid upload/storage budget.')
        if min(self.user_quota_bytes, self.teacher_quota_bytes) <= 0:
            raise ValueError('User quotas must be positive.')
        if not (1 <= self.pool_size <= 10 and 0 <= self.max_overflow <= 5):
            raise ValueError('Invalid database pool size.')
        if self.codeforces_profile_ttl_seconds < 21600 or self.codeforces_contest_ttl_seconds < 900:
            raise ValueError('Codeforces cache intervals must respect the documented application budget.')

    @classmethod
    def from_env(cls) -> 'Settings':
        data = Path(os.getenv('DATA_DIR', str(ROOT / '.data'))).resolve()
        data.mkdir(parents=True, exist_ok=True, mode=0o700)
        production = os.getenv('APP_ENV', 'development') == 'production'
        secret = os.getenv('APP_SECRET', '')
        origin = os.getenv('APP_ORIGIN', 'http://localhost:8000').rstrip('/')
        if production and (len(secret) < 32 or not origin.startswith('https://')):
            raise RuntimeError('Production requires APP_SECRET (32+ characters) and an HTTPS APP_ORIGIN.')
        if not secret:
            import secrets
            secret_file = data / 'session-secret'
            if not secret_file.exists():
                try:
                    fd = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'w') as f:
                        f.write(secrets.token_hex(32))
                except FileExistsError:
                    pass
            secret = secret_file.read_text().strip()
        return cls(os.getenv('DATABASE_URL', f'sqlite:///{data / "olympiados.db"}'), data, secret, production, origin,
            user_quota_bytes=int(os.getenv('USER_QUOTA_BYTES', str(32 * 1024 * 1024))),
            teacher_quota_bytes=int(os.getenv('TEACHER_QUOTA_BYTES', str(128 * 1024 * 1024))),
            db_schema=os.getenv('DB_SCHEMA', 'olympiados'), pool_size=int(os.getenv('DB_POOL_SIZE', '2')),
            max_overflow=int(os.getenv('DB_MAX_OVERFLOW', '1')), storage_backend=os.getenv('STORAGE_BACKEND', 'local'),
            supabase_url=os.getenv('SUPABASE_URL', '').rstrip('/'),
            supabase_storage_bucket=os.getenv('SUPABASE_STORAGE_BUCKET', 'olympiados-attachments'),
            supabase_storage_server_key=os.getenv('SUPABASE_STORAGE_SERVER_KEY', ''),
            storage_hard_limit_bytes=int(os.getenv('STORAGE_HARD_LIMIT_BYTES', str(700 * 1024 * 1024))),
            storage_soft_limit_bytes=int(os.getenv('STORAGE_SOFT_LIMIT_BYTES', str(500 * 1024 * 1024))),
            circles_enabled=os.getenv('CIRCLES_ENABLED', 'true').lower() == 'true',
            codeforces_enabled=os.getenv('CODEFORCES_ENABLED', 'true').lower() == 'true',
            codeforces_sync_enabled=os.getenv('CODEFORCES_SYNC_ENABLED', 'false').lower() == 'true',
            codeforces_profile_ttl_seconds=int(os.getenv('CODEFORCES_PROFILE_TTL_SECONDS', '21600')),
            codeforces_contest_ttl_seconds=int(os.getenv('CODEFORCES_CONTEST_TTL_SECONDS', '1200')))
