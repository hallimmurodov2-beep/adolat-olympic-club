"""Operator commands. No account or classroom is created implicitly at startup."""
from __future__ import annotations
import argparse
import getpass
import os
import secrets
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from .config import ROOT, Settings
from .db import make_engine
from .models import AuthSession, AuditLog, Event, RateLimit, StoredFile, User, now_ms
from .security import hash_password
from .seed import initialize, seed_demo


def migrate(settings: Settings):
    config = Config(str(ROOT / 'alembic.ini'))
    config.set_main_option('script_location', str(ROOT / 'migrations'))
    config.set_main_option('sqlalchemy.url', settings.database_url.replace('%', '%%'))
    config.attributes['explicit_url'] = True
    config.attributes['settings'] = settings
    command.upgrade(config, 'head')
    if settings.database_url.startswith('sqlite:///'):
        file = Path(settings.database_url.removeprefix('sqlite:///'))
        if file.exists():
            file.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description='Adolat Olympic Club operator tools')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check', help='Check schema and production runtime boundary without DDL')
    commands.add_parser('reconcile-uploads', help='Reconcile expired upload reservations without deleting committed work')
    commands.add_parser('init', help='Apply migrations and initialize subjects/settings')
    bootstrap = commands.add_parser('admin', help='Create the first administrator (no public signup)')
    bootstrap.add_argument('--email', required=True)
    bootstrap.add_argument('--name', required=True)
    bootstrap.add_argument('--locale', choices=['ru', 'en'], default='ru')
    demo = commands.add_parser('demo', help='Seed clearly identified, original demonstration data')
    demo.add_argument('--password', default=os.getenv('DEMO_PASSWORD'))
    reset = commands.add_parser('reset-password', help='Operator-assisted account recovery; revokes all sessions')
    reset.add_argument('--email', required=True)
    commands.add_parser('cleanup', help='Remove expired sessions, old invalidation events and orphan files')
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.command == 'init':
        migrate(settings)
    engine = make_engine(settings)
    if args.command == 'check':
        from .services.readiness import check_ready
        try:
            print(check_ready(engine, settings, security=settings.production))
        finally:
            engine.dispose()
        return
    if args.command == 'reconcile-uploads':
        from types import SimpleNamespace
        from sqlalchemy.orm import sessionmaker
        from .services.storage import build_storage
        from .services.uploads import reconcile
        app = SimpleNamespace(state=SimpleNamespace(settings=settings, sessions=sessionmaker(engine, expire_on_commit=False), storage=build_storage(settings)))
        try:
            print(reconcile(app))
        finally:
            engine.dispose()
        return
    with Session(engine) as db:
        if args.command == 'init':
            initialize(db)
            print('Database initialized. Create an administrator or explicitly seed demo data.')
        elif args.command == 'admin':
            if db.scalar(select(User.id).where(User.role == 'admin').limit(1)):
                raise SystemExit('An administrator already exists. This command is only for initial bootstrap.')
            password = getpass.getpass('Administrator password (12+ characters): ')
            if len(password) < 12:
                raise SystemExit('Password is too short.')
            from .schemas import InviteInput
            email = InviteInput(email=args.email, role='student').email
            user = User(email=email, display_name=args.name, password_hash=hash_password(password), role='admin', locale=args.locale)
            db.add(user)
            print('Administrator created. Sign in, then invite teachers and students.')
        elif args.command == 'demo':
            if settings.production:
                raise SystemExit('Demo seeding is disabled in production.')
            password = args.password or secrets.token_urlsafe(18)
            accounts = seed_demo(db, password)
            print('DEMONSTRATION DATA — not real school records')
            for handle, email in accounts.items():
                print(f'{handle:12} {email}')
            if args.password is None:
                print('Generated demo password:', password)
            else:
                print('All demo accounts use the password explicitly supplied to this command.')
        elif args.command == 'reset-password':
            user = db.scalar(select(User).where(User.email == args.email.strip().casefold()))
            if not user:
                raise SystemExit('Account not found.')
            password = getpass.getpass('New password (12+ characters): ')
            if len(password) < 12:
                raise SystemExit('Password is too short.')
            user.password_hash = hash_password(password)
            db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
            db.add(AuditLog(actor_id=user.id, action='operator.password_reset', entity_id=user.id))
            print('Password changed and all sessions revoked. Verify identity out of band before sharing access.')
        elif args.command == 'cleanup':
            db.execute(delete(AuthSession).where(AuthSession.expires_at < now_ms()))
            db.execute(delete(Event).where(Event.created_at < now_ms() - 7*86400000))
            db.execute(delete(RateLimit).where(RateLimit.window < now_ms()//1000 - 2*86400))
            from .models import UploadIntent
            known = set(db.scalars(select(StoredFile.id))) | set(db.scalars(select(UploadIntent.id)))
            directory = settings.data_dir / 'uploads'
            count = 0
            if settings.storage_backend == 'local' and directory.exists():
                for file in directory.iterdir():
                    # A grace period avoids deleting a file from an in-flight upload.
                    if file.is_file() and file.name not in known and file.stat().st_mtime < now_ms()/1000 - 86400:
                        file.unlink(); count += 1
            print(f'Expired sessions/events cleaned; {count} orphan files removed. Student work was not deleted. Run reconcile-uploads separately for intent accounting.')
        db.commit()
    engine.dispose()

if __name__ == '__main__':
    main()
