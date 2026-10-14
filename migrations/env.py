"""Frozen V1 baseline executes only inside the configured private PostgreSQL schema.
SQLite keeps ordinary unqualified names. Runtime startup never invokes this file.
"""
from logging.config import fileConfig
from dataclasses import replace
from alembic import context
from sqlalchemy import text
from server.config import Settings
from server.db import make_engine, assert_schema
from server.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
settings = config.attributes.get('settings') or Settings.from_env()
if config.attributes.get('explicit_url'):
    # Operator tooling may pass a separate migration URL. Settings used here are
    # development-mode connection settings, not an attempt to start the web app.
    settings = replace(settings, database_url=config.get_main_option('sqlalchemy.url'), production=False)
else:
    import os
    settings = replace(settings, database_url=os.getenv('MIGRATION_DATABASE_URL', settings.database_url), production=False)
config.set_main_option('sqlalchemy.url', settings.database_url.replace('%', '%%'))
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    # Alembic owns its migration marker; it is not an application model table.
    return not (type_ == 'table' and name == 'alembic_version' and reflected)


def run_migrations_offline():
    postgres = not settings.database_url.startswith('sqlite')
    context.configure(url=config.get_main_option('sqlalchemy.url'), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={'paramstyle': 'named'}, render_as_batch=not postgres,
                      version_table_schema=settings.db_schema if postgres else None)
    with context.begin_transaction():
        if postgres:
            context.execute(f'SET search_path TO "{settings.db_schema}"')
        context.run_migrations()


def run_migrations_online():
    engine = make_engine(settings)
    with engine.connect() as connection:
        assert_schema(connection, settings.db_schema)
        postgres = connection.dialect.name == 'postgresql'
        if postgres:
            connection.dialect.default_schema_name = settings.db_schema
            connection.execute(text("SET statement_timeout = '0'"))
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=not postgres, compare_type=True,
                          include_object=include_object,
                          version_table_schema=settings.db_schema if postgres else None)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
