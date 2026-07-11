.PHONY: test lint format format-check run setup setup-dev benchmark benchmark-mock

setup:
	pip install -r requirements.txt

setup-dev:
	pip install -r requirements.txt && pip install ruff && npm install

test:
	pytest

lint:
	ruff check src/ legalist/ server.py --max-line-length=120

format:
	ruff format src/ legalist/ server.py

format-check:
	ruff format --check src/ legalist/ server.py

run:
	uvicorn server:app --reload --port 8000

benchmark:
	python legalist/benchmark.py

benchmark-mock:
	python legalist/benchmark.py --mock
