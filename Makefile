.PHONY: help install setup run test clean migrate docker-up docker-down

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
