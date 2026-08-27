# Everything you need to run this app, in one place.
#
#   make            list the targets
#   make setup      once, after cloning
#   make start      database up and migrated
#   make api        backend   (leave running)
#   make web        frontend  (leave running, second terminal)
#
# Nothing here is magic -- each target is the same command the README explains,
# and `make -n <target>` prints what it would run without running it. The point
# is the ORDER, which is the part that was easy to get wrong.
#
# Targets that touch the backend use backend/.venv directly rather than asking
# you to activate it first. Forgetting to activate a virtualenv is the single
# most common way this goes wrong, and it fails in a confusing way.

VENV := backend/.venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
BACKUP := backup-$(shell date +%F).sql

.DEFAULT_GOAL := help
.PHONY: help setup start db migrate api web test backup restore stop reset-db

help:
	@echo "Setup"
	@echo "  make setup      create the virtualenv, install backend and frontend deps"
	@echo ""
	@echo "Running it (needs two terminals)"
	@echo "  make start      start Postgres and apply migrations"
	@echo "  make api        run the backend on :8000   (leave it running)"
	@echo "  make web        run the frontend on :5173  (leave it running)"
	@echo ""
	@echo "Day to day"
	@echo "  make test       run the test suite"
	@echo "  make migrate    apply new migrations"
	@echo "  make backup     snapshot the database to $(BACKUP)"
	@echo "  make restore FILE=backup-....sql   restore into an empty database"
	@echo "  make stop       stop Postgres, keeping the data"
	@echo "  make reset-db   DELETE all local data and start over"

# --- once, after cloning ---------------------------------------------------

setup:
	python3 -m venv $(VENV)
	$(PIP) install --quiet --upgrade pip
	cd backend && .venv/bin/pip install -e ".[dev]"
	cd frontend && npm install
	@echo ""
	@echo "Done. Next:  make start"

# --- running it ------------------------------------------------------------

start: db migrate
	@echo ""
	@echo "Database ready. Now, in two terminals:  make api  /  make web"

db:
	# --wait blocks until the healthcheck passes. Without it `up -d` returns
	# several seconds before Postgres accepts connections, and whatever runs
	# next fails with "connection refused".
	docker compose up -d --wait

migrate: guard-venv
	cd backend && .venv/bin/alembic upgrade head

api: guard-venv
	cd backend && .venv/bin/uvicorn api.main:app --reload

web:
	cd frontend && npm run dev

# --- day to day ------------------------------------------------------------

test: guard-venv
	cd backend && .venv/bin/pytest -q

backup:
	docker compose exec -T db pg_dump -U golf golf > $(BACKUP)
	@wc -l $(BACKUP)
	@echo "^ a real backup is hundreds of lines. A handful means it captured nothing."

restore:
	@test -n "$(FILE)" || (echo "Usage: make restore FILE=backup-2026-08-27.sql"; exit 1)
	@test -f "$(FILE)" || (echo "No such file: $(FILE)"; exit 1)
	docker compose down -v
	docker compose up -d --wait
	docker compose exec -T db psql -U golf -d golf < $(FILE)

stop:
	docker compose down

reset-db:
	@echo "This DELETES every course and round in your local database."
	@echo "Take a snapshot first with: make backup"
	@read -p "Type yes to continue: " ok && [ "$$ok" = "yes" ]
	docker compose down -v
	$(MAKE) db migrate

# --- internal --------------------------------------------------------------

guard-venv:
	@test -x $(PY) || (echo "No virtualenv yet. Run: make setup"; exit 1)
