# Thin shims over docker compose. The contract is Docker -- every target below
# is one compose command and you can run them directly.

.DEFAULT_GOAL := help
.PHONY: help up stop down test ads logs psql clean

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

up: ## Build and run the app at http://localhost:8088
	docker compose up --build

# `--profile test` so db-test is included: `make test` leaves it running, and
# a plain `docker compose stop` only reaches services in the default profile.
stop: ## Stop all services, keeping containers and data (`make up` resumes)
	docker compose --profile test stop

down: ## Stop and remove the containers (the database volume survives)
	docker compose --profile test down

test: ## Run the test suite
	docker compose --profile test run --rm tests

ads: ## Write outputs/ads.md for all seven sample ads
	docker compose run --rm app python -m scripts.run_all_ads

logs: ## Tail the app logs
	docker compose logs -f app

psql: ## Open a psql shell on the running database
	docker compose exec db psql -U adcheck -d adcheck

clean: ## Stop and delete the database volume (forces a fresh ingest)
	docker compose down -v
