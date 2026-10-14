from __future__ import annotations
from collections.abc import Generator
from fastapi import Request
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from .config import Settings


def make_engine(settings: Settings):
    url = make_url(settings.database_url)
    sqlite = url.get_backend_name() == 'sqlite'
    if not sqlite and url.drivername == 'postgresql':
        url = url.set(drivername='postgresql+psycopg')
    options = {'pool_pre_ping': True}
    if sqlite:
        options['connect_args'] = {'check_same_thread': False, 'timeout': 15}
    else:
        options.update(pool_size=settings.pool_size, max_overflow=settings.max_overflow, pool_timeout=10, pool_recycle=1800,
                       connect_args={'connect_timeout': 10})
    engine = create_engine(url, **options)
    if sqlite:
        @event.listens_for(engine, 'connect')
        def configure_sqlite(connection, _):
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA busy_timeout=15000')
            cursor.close()
    else:
        @event.listens_for(engine, 'connect')
        def configure_postgres(connection, _):
            before = connection.autocommit
            connection.autocommit = True
            with connection.cursor() as cursor:
                # Validated identifier, fixed session search path; public is excluded.
                cursor.execute(f'SET SESSION search_path TO "{settings.db_schema}"')
                cursor.execute("SET SESSION statement_timeout TO '15s'")
                cursor.execute("SET SESSION lock_timeout TO '5s'")
                cursor.execute("SET SESSION idle_in_transaction_session_timeout TO '30s'")
            connection.autocommit = before
    return engine


def assert_schema(connection, schema):
    if connection.dialect.name != 'sqlite':
        current = connection.scalar(text('select current_schema()'))
        if current != schema:
            raise RuntimeError('Private application schema is missing or inaccessible. Run operator bootstrap; no public fallback is permitted.')


def get_db(request: Request) -> Generator[Session, None, None]:
    with request.app.state.sessions() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
