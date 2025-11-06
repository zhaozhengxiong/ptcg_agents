
.PHONY: install test fmt lint run cov

install:
	poetry install

test:
	poetry run pytest

fmt:
	poetry run black .
	poetry run isort .

lint:
	poetry run mypy core env agents

run:
	poetry run python scripts/example_run.py

cov:
	poetry run pytest --cov --cov-report=html
	@echo "HTML coverage report at: htmlcov/index.html"
