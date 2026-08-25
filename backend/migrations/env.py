"""Alembic's entry point: how a migration finds the database and the models.

What a migration is, and why create_all is not enough
-----------------------------------------------------
`Base.metadata.create_all` only ever CREATES. Point it at a database whose
`rounds` table already exists and it does nothing at all -- so the moment a
column is added, renamed or retyped, the code and the database silently disagree
and the next query fails with something unhelpful.

A migration is a recorded, ordered change: "add this column", "drop that index".
Alembic keeps a table called `alembic_version` holding the revision the database
is currently at, so it can work out which changes still need applying. That makes
schema changes repeatable across a laptop and a deployed server, and -- the
reason this went in before the backfill -- it makes them possible *without
destroying the rows already there*.

Alembic can write most migrations itself, by comparing `target_metadata` below
against the live database and emitting the difference. Always read what it
generates; autogenerate is good at columns and indexes and blind to things like
a column rename, which it will happily represent as a drop plus an add.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importing db.config rather than db.session on purpose: session builds an
# Engine at import time, and Alembic wants to build its own.
from db.config import database_url
from db.models import Base

config = context.config

# The URL is injected here rather than written into alembic.ini, because the
# real one carries a password and differs per environment. Same single source of
# truth the app itself uses.
#
# A URL already set on the config wins, so a programmatic caller -- the drift
# test, chiefly -- can point a migration run at a scratch database without
# having to manipulate the environment.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", database_url())

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# What autogenerate compares the database against. Every model has to be
# imported for its table to appear here -- importing db.models is enough,
# because they all live in that one module.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it.

    `alembic upgrade head --sql` produces a script a DBA can review and run by
    hand. Not needed for this project, but it is why the two functions exist.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect and apply the migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Without this, Alembic ignores a column whose type changed --
            # Numeric(4,1) to Numeric(5,1) would pass silently.
            compare_type=True,
            # Likewise for a DEFAULT added or removed at the database level.
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
