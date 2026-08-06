# Makefile for review_langchain

.PHONY: help install env db-up db-down db-wait run run-web

help:
	@echo "Targets: install, env, db-up, db-down, db-wait, run, run-web"

install:
	python -m pip install -r requirements.txt

# Create .env from example if missing
env:
	[ -f .env ] || cp .env.example .env && echo "Created .env from .env.example (edit as needed)"

# Start PostgreSQL (via docker-compose)
db-up:
	docker-compose up -d

# Stop and remove containers
db-down:
	docker-compose down

# Wait for Postgres service to accept connections (uses docker-compose exec pg_isready)
db-wait:
	@echo "Waiting for Postgres to be ready..."
	@bash -c 'until docker-compose exec -T db pg_isready -U "${POSTGRES_USER:-postgres}" >/dev/null 2>&1; do sleep 1; printf "."; done; echo "\nPostgres is ready."'

# Run CLI app (reads one review from stdin)
run:
	python main.py

# Run web app
run-web:
	python app.py
