"""Where the database URL comes from. Deliberately free of side effects.

Separate from session.py because importing that module builds an Engine, and
some callers -- the test suite, chiefly -- need to read the configured URL and
change it *before* any engine exists.
"""

import os

from dotenv import load_dotenv

# Loads backend/.env if present. Real environment variables always win, so a
# deployed setting is never overridden by a stray local file.
load_dotenv()

# Matches the docker-compose.yml at the repo root, so a fresh clone needs no
# configuration at all.
DEFAULT_DATABASE_URL = "postgresql+psycopg://golf:golf@127.0.0.1:5432/golf"


def database_url() -> str:
    """The database to connect to. Read at call time, not at import time."""
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
