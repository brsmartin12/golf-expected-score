"""Create every table, for local development.

    python -m db.create_tables

A stopgap, and knowingly so. `create_all` only ever CREATES -- it will not alter
a table that already exists, so the moment a column changes it silently does
nothing and the code starts disagreeing with the database.

That is tolerable while the only data is throwaway. It stops being tolerable at
the backfill, because thirty hand-entered rounds are data worth keeping, and
from then on a schema change has to be a migration that preserves them. Alembic
goes in before that point -- it can autogenerate its first migration from these
same models, so nothing here is wasted.
"""

from db.models import Base
from db.session import DATABASE_URL, engine


def main() -> None:
    # Hides the password before printing, so the URL can be logged safely.
    print(f"Creating tables in {engine.url.render_as_string(hide_password=True)}")
    Base.metadata.create_all(engine)
    print("Done:", ", ".join(t.name for t in Base.metadata.sorted_tables))


if __name__ == "__main__":
    main()
