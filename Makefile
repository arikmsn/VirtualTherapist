.PHONY: help install setup run test clean migrate migrate-prod check-migration verify-rls docker-up docker-down

help:
	@echo "TherapyCompanion.AI - Development Commands"
	@echo ""
	@echo "Usage:"
	@echo "  make install      Install dependencies"
	@echo "  make setup        Setup environment and database"
	@echo "  make run          Run the application"
	@echo "  make test         Run tests"
	@echo "  make migrate      Run database migrations"
	@echo "  make clean        Clean up generated files"
	@echo "  make docker-up    Start with Docker Compose"
	@echo "  make docker-down  Stop Docker Compose"
	@echo ""

install:
	pip install -r requirements.txt

setup:
	cp .env.example .env
	@echo "Please edit .env with your configuration"
	@echo "Then run: make migrate"

migrate:
	alembic upgrade head

# Run migrations against Supabase production.
# Requires PROD_DATABASE_URL to be set in your shell (never committed to .env):
#   export PROD_DATABASE_URL="postgresql://postgres:PASSWORD@db.PROJECTREF.supabase.co:5432/postgres?sslmode=require"
#   make migrate-prod
migrate-prod:
	@if [ -z "$(PROD_DATABASE_URL)" ]; then \
		echo "ERROR: PROD_DATABASE_URL is not set. Export it in your shell first."; \
		exit 1; \
	fi
	DATABASE_URL=$(PROD_DATABASE_URL) alembic upgrade head

# Show current migration revision on whichever DATABASE_URL is active.
check-migration:
	alembic current

# Pretty-print the RLS policy check query so you can paste it into the
# Supabase SQL Editor.  Actual execution requires a database connection.
verify-rls:
	@echo ""
	@echo "=== RLS Verification Query (paste into Supabase SQL Editor) ==="
	@echo ""
	@cat scripts/verify_rls.sql
	@echo ""

run:
	python -m app.main

test:
	pytest -v

test-cov:
	pytest --cov=app tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f app

format:
	black app/ tests/
	isort app/ tests/

lint:
	flake8 app/ tests/
	mypy app/
