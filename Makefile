# Convenience targets. On Windows use Git Bash, WSL, or run the underlying
# commands directly (see README).

COMPOSE      := docker compose
COMPOSE_PROD := docker compose -f docker-compose.prod.yml

.PHONY: help up down build logs ps migrate makemigrations superuser shell test lint fmt prod-up prod-down

help:
	@echo "Targets:"
	@echo "  up            Build & start the dev stack"
	@echo "  down          Stop the dev stack"
	@echo "  logs          Tail backend logs"
	@echo "  migrate       Apply migrations"
	@echo "  makemigrations Create migrations"
	@echo "  superuser     Create a Django superuser"
	@echo "  shell         Open a Django shell in the web container"
	@echo "  test          Run the backend test suite"
	@echo "  lint / fmt    Ruff lint / format"
	@echo "  prod-up       Build & start the production stack"

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

build:
	$(COMPOSE) build

logs:
	$(COMPOSE) logs -f web

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec web python manage.py migrate

makemigrations:
	$(COMPOSE) exec web python manage.py makemigrations

superuser:
	$(COMPOSE) exec web python manage.py createsuperuser

shell:
	$(COMPOSE) exec web python manage.py shell

test:
	$(COMPOSE) exec web pytest

lint:
	$(COMPOSE) exec web ruff check .

fmt:
	$(COMPOSE) exec web ruff format .

prod-up:
	$(COMPOSE_PROD) up --build -d

prod-down:
	$(COMPOSE_PROD) down
