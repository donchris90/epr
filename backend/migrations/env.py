"""
Alembic environment — wired to the Flask-Migrate app context so
`flask db migrate` / `flask db upgrade` work out of the box.

Reminder (SRS Section 5.5): any migration that creates a new
tenant-scoped table MUST also include:

    op.execute("ALTER TABLE <table> ENABLE ROW LEVEL SECURITY")
    op.execute('''
        CREATE POLICY tenant_isolation ON <table>
        USING (tenant_id = current_setting('app.tenant_id')::uuid)
    ''')

RLS is DDL and will not be generated automatically by --autogenerate;
it must be added by hand to every migration touching a tenant-scoped
table.
"""
import logging
from logging.config import fileConfig

from flask import current_app
from alembic import context

config = context.config
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")


def get_engine():
    return current_app.extensions["migrate"].db.get_engine()


def get_engine_url():
    return get_engine().url.render_as_string(hide_password=False).replace("%", "%%")


config.set_main_option("sqlalchemy.url", get_engine_url())
target_db = current_app.extensions["migrate"].db


def get_metadata():
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=get_metadata(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No changes in schema detected.")

    connectable = get_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            process_revision_directives=process_revision_directives,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
