.PHONY: help db-up db-down migrate seed verify test shell clean

help:
	@echo "Django Primitives Testbed"
	@echo ""
	@echo "Usage:"
	@echo "  make db-up       Start PostgreSQL container"
	@echo "  make db-down     Stop PostgreSQL container"
	@echo "  make migrate     Apply all migrations"
	@echo "  make seed        Seed testbed with sample data"
	@echo "  make verify      Run integrity verification"
	@echo "  make test        Run pytest test suite"
	@echo "  make shell       Open Django shell"
	@echo "  make run         Run development server"
	@echo "  make clean       Remove database volume"
	@echo ""
	@echo "Quick Start:"
	@echo "  make db-up migrate seed verify"

db-up:
	docker compose up -d db
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 3
	@docker compose exec db pg_isready -U postgres -d primitives_testbed || (echo "Database not ready" && exit 1)
	@echo "PostgreSQL is ready!"

db-down:
	docker compose down

migrate:
	python manage.py migrate

seed:
	python manage.py seed_testbed

verify:
	python manage.py verify_integrity

test:
	pytest tests/ -v

shell:
	python manage.py shell

run:
	python manage.py runserver

clean:
	docker compose down -v
	@echo "Database volume removed"

# Full setup from scratch
setup: db-up
	@sleep 2
	$(MAKE) migrate
	$(MAKE) seed
	@echo ""
	@echo "Setup complete! Run 'make verify' to check integrity constraints."
