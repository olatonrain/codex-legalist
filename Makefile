.PHONY: test lint run setup

setup:
	pip install -r requirements.txt

test:
	pytest

lint:
	python -m flake8 src/ legalis/ server.py --max-line-length=120

run:
	uvicorn server:app --reload --port 8000
