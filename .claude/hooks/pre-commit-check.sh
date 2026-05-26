#!/usr/bin/env bash
set -euo pipefail

echo "Running pre-commit checks..."

# Run lint
ruff check .

# Run type checking
mypy src/

# Run tests
pytest tests/ -v --tb=short

echo "All checks passed!"
