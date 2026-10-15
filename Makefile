.PHONY: init up down test lint web-build examples
init:
	python3 infrastructure/init.py
up:
	docker compose up --build -d
down:
	docker compose down
test:
	pytest -q
lint:
	ruff check apps/api tests
web-build:
	cd apps/web && npm ci && npm run build
examples:
	python3 infrastructure/package_examples.py
acceptance:
	python infrastructure/acceptance.py --restart
