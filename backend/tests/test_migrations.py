"""Tests that the migrations and the models say the same thing.

This is the test the whole Alembic setup exists for. `Base.metadata.create_all`
builds the schema from the models; a deployed database is built by replaying
migrations. If those two ever disagree, the app works locally and fails in
production with a missing column — the exact failure that is worst to diagnose,
because the code is fine and the tests pass.

Rather than trusting that whoever changes a model remembers to write a migration,
this applies the migrations to an empty database and asks Alembic itself whether
anything is still different.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from db.config import database_url
from db.models import Base
from tests.conftest import requires_database

pytestmark = requires_database

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRATCH_DB = "golf_migration_check"


@pytest.fixture
def migrated_engine():
    """An empty database with the migrations applied, dropped afterwards.

    Its own database rather than the test one, because this needs a schema built
    only by migrations — the test database's tables come from create_all.
    """
    base = make_url(database_url())
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    scratch = base.set(database=SCRATCH_DB)

    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
        connection.execute(text(f'CREATE DATABASE "{SCRATCH_DB}"'))

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", scratch.render_as_string(hide_password=False))

    engine = create_engine(scratch)
    try:
        command.upgrade(config, "head")
        yield engine, config
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
        admin.dispose()


def test_migrations_produce_exactly_the_models(migrated_engine):
    """The one that catches a model changed without a migration written.

    compare_metadata is the same comparison `alembic revision --autogenerate`
    runs. An empty diff means replaying the migrations lands on precisely the
    schema the models describe.
    """
    engine, _ = migrated_engine

    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={"compare_type": True, "compare_server_default": True},
        )
        differences = compare_metadata(context, Base.metadata)

    assert differences == [], (
        "The models and the migrations disagree. Run:\n"
        "    cd backend && alembic revision --autogenerate -m 'describe the change'\n"
        f"Alembic found: {differences}"
    )


def test_every_table_is_created_by_the_migrations(migrated_engine):
    """Guards against a model that exists but was never imported where Alembic
    can see it, which autogenerate would silently skip."""
    engine, _ = migrated_engine
    expected = {t.name for t in Base.metadata.sorted_tables}

    with engine.connect() as connection:
        actual = set(
            connection.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        )

    assert expected <= actual
    assert "alembic_version" in actual  # the revision pointer itself


def test_the_migrations_can_be_rolled_all_the_way_back(migrated_engine):
    """A downgrade nobody has ever run is a downgrade that does not work.

    This matters at the moment it is needed: a migration applied to a database
    holding real rounds, that then has to be undone.
    """
    engine, config = migrated_engine

    command.downgrade(config, "base")

    with engine.connect() as connection:
        remaining = set(
            connection.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        )

    # Only Alembic's own bookkeeping table should survive.
    assert remaining == {"alembic_version"}
