.PHONY: lint lint-fix test check-all help install venv-init

help:
	@echo "Available targets:"
	@echo "  make venv-init   - Create virtual environment and install dependencies"
	@echo "  make lint        - Run linting checks (flake8, black, isort)"
	@echo "  make lint-fix    - Auto-fix formatting issues (black, isort)"
	@echo "  make test        - Run unit tests with coverage"
	@echo "  make check-all   - Run linting and tests"
	@echo ""
	@echo "First run: make venv-init"

venv-init:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt && pip install flake8 black isort pytest pytest-cov
	@echo "✓ Virtual environment created. Activate with: source venv/bin/activate"

install: venv-init

lint:
	. venv/bin/activate && flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics && black --check . && isort --check .

lint-fix:
	. venv/bin/activate && black . && isort .

test:
	. venv/bin/activate && pytest tests/ -v --cov=. --cov-report=xml --cov-report=term

check-all:
	. venv/bin/activate && (flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics && black --check . && isort --check . && pytest tests/ -v --cov=. --cov-report=xml --cov-report=term) && echo "✓ All checks passed"
