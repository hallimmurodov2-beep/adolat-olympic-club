"""Fail-closed runtime checks. This module never migrates or creates tables."""
from sqlalchemy import text
from ..db import assert_schema
from ..models import Base

SCHEMA_REVISION = 'd84f103f71aa'


def check_ready(engine, settings, security=False):
    with engine.connect() as conn:
        assert_schema(conn, settings.db_schema)
        revision = conn.scalar(text('SELECT version_num FROM alembic_version'))
        if revision != SCHEMA_REVISION:
            raise RuntimeError('Schema revision mismatch. Run the approved operator migration first.')
        if security and conn.dialect.name == 'postgresql':
            role = conn.execute(text('SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
            if any(role):
                raise RuntimeError('The web runtime role must not have administrative database capabilities.')
            if conn.scalar(text('SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)')):
                raise RuntimeError('Runtime must not have inherited or assumable role memberships.')
            if conn.scalar(text("SELECT has_database_privilege(current_user, current_database(), 'CREATE') OR has_schema_privilege(current_user, 'public', 'CREATE')")):
                raise RuntimeError('Runtime must not be able to create persistent schemas or public tables.')
            if conn.scalar(text('SELECT has_schema_privilege(current_user, :s, \'CREATE\')'), {'s':settings.db_schema}):
                raise RuntimeError('Runtime must not own or create in the application schema.')
            rows = conn.execute(text("SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, c.relowner = (SELECT oid FROM pg_roles WHERE rolname=current_user) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:s AND c.relkind='r'"), {'s':settings.db_schema}).all()
            actual = {r[0]:r for r in rows}
            for name in Base.metadata.tables:
                if name not in actual or not actual[name][1] or not actual[name][2] or actual[name][3]:
                    raise RuntimeError('Application table policies/ownership do not match the restricted runtime contract.')
            leaked = conn.scalar(text("SELECT count(*) FROM pg_roles WHERE rolname IN ('anon','authenticated') AND has_schema_privilege(oid, :s, 'USAGE')"), {'s':settings.db_schema})
            if leaked:
                raise RuntimeError('Browser database roles must not have application schema access.')
    return {'status':'ready', 'schema_revision':SCHEMA_REVISION}
